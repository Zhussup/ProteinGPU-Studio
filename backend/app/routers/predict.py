"""Predict + mutate + scan endpoints (jobs)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ml.folding.base import AA_RE as AA_ALPHABET, mutant_sequence  # noqa: E402
from ..schemas import (  # noqa: E402
    MutationResult, PredictRequest, PredictResponse, RmsdResult, MutateRequest,
    ScanRequest, ScanResponse, ScanRow, interpret_rmsd,
)
from ..config import get_settings  # noqa: E402
from ..services.align_service import align_pair  # noqa: E402
from ..services.folding_service import get_folding_service  # noqa: E402
from ..services.job_manager import Job, get_job_manager  # noqa: E402
from ..services.pdb_io import parse_ca_coords  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["folding"])


def _stage(job: Job, jm, message: str, progress: float) -> None:
    """Record a real pipeline stage; pollers read it via GET /jobs/{id}."""
    job.message = message
    job.progress = progress
    jm.update(job)


def _prepare_model(job: Job, svc) -> None:
    """Apply the requested per-request profile (inside the GPU semaphore)."""
    profile = job.params.get("profile")
    if profile and profile != "auto" and profile != svc.profile:
        svc.set_profile(profile)


def _jm():
    return get_job_manager()


def _run_predict(job: Job) -> dict:
    svc = get_folding_service()
    jm = _jm()
    seq = job.params["sequence"]
    _stage(job, jm, "подготовка модели", 0.03)
    _prepare_model(job, svc)
    _ = svc.model  # force weight load under the "подготовка" message
    _stage(job, jm, "инференс WT", 0.1)
    res, from_cache = svc.predict_cached(seq)
    _stage(job, jm, "сохранение PDB", 0.9)
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(res.pdb_text)
    return {
        "length": len(seq), "model": svc.model_name, "from_cache": from_cache,
        "plddt_mean": res.plddt_mean,
        "plddt_list": [float(x) for x in res.plddt],
        "pdb_file": "wt.pdb",
    }


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    job_id = _jm().submit(
        kind="predict", params={"sequence": req.sequence, "profile": req.profile},
        run_fn=_run_predict,
        use_gpu=bool(req.profile) or _gpu_needed())
    return PredictResponse(job_id=job_id, status="queued",
                           length=len(req.sequence))


def _gpu_needed() -> bool:
    """A resident real model must be serialized even for the cpu profile —
    it is the same singleton object. Dummy-model tests stay on the CPU pool."""
    return "omegafold" in get_folding_service().model_name


@router.post("/mutate", response_model=MutationResult)
def mutate(req: MutateRequest) -> MutationResult:
    seq = req.sequence
    if seq[req.position - 1] == req.mutant_aa:
        raise HTTPException(422, "mutant residue equals WT residue at that position")
    job_id = _jm().submit(
        kind="mutate",
        params={"sequence": seq, "position": req.position,
                "mutant_aa": req.mutant_aa, "profile": req.profile},
        run_fn=_run_mutate,
        use_gpu=bool(req.profile) or _gpu_needed())
    return MutationResult(
        job_id=job_id, status="queued", wt_sequence=seq,
        mutant_sequence=mutant_sequence(seq, req.position, req.mutant_aa),
        position=req.position, wt_aa=seq[req.position - 1],
        mutant_aa=req.mutant_aa)


def _run_mutate(job: Job) -> dict:
    settings = get_settings()
    svc = get_folding_service()
    jm = _jm()
    seq: str = job.params["sequence"]
    pos: int = job.params["position"]
    mut_aa: str = job.params["mutant_aa"]
    mut_seq = mutant_sequence(seq, pos, mut_aa)

    _stage(job, jm, "подготовка модели", 0.03)
    _prepare_model(job, svc)
    _ = svc.model  # force weight load under the "подготовка" message
    if svc.cache.get(seq, svc.model_name) is None:
        _stage(job, jm, "инференс WT", 0.1)  # skipped message if cache hit
    wt, wt_cached = svc.predict_cached(seq)
    _stage(job, jm, "инференс мутанта", 0.5)
    mut = svc.model.predict(mut_seq)
    _stage(job, jm, "запись PDB-файлов", 0.8)

    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(wt.pdb_text)
    (out_dir / "mut.pdb").write_text(mut.pdb_text)

    # Align mutant ONTO WT in the WT frame; write pre-aligned mutant PDB.
    _stage(job, jm, "наложение Кабша (C++/CUDA)", 0.85)
    al = align_pair(parse_ca_coords(wt.pdb_text), parse_ca_coords(mut.pdb_text),
                    position=pos, radius=settings.local_radius)
    from ..services.align_service import write_aligned_pdb
    import hpc_core
    full = hpc_core.kabsch(mut.coords_ca, wt.coords_ca)
    (out_dir / "mut_aligned.pdb").write_text(
        write_aligned_pdb(mut.pdb_text, full.R, full.t))

    _stage(job, jm, "метрики", 0.95)
    rmsd = RmsdResult(
        global_rmsd=al.global_rmsd, local_rmsd=al.local_rmsd,
        local_window=al.local_window, tm_score=al.tm_score,
        plddt_wt=wt.plddt_mean, plddt_mut=mut.plddt_mean,
        interpretation=interpret_rmsd(al.local_rmsd, settings.rmsd_stable_below,
                                      settings.rmsd_critical_above),
        engine=al.engine)
    from ..services.summary import make_summary
    return {
        "wt_sequence": seq, "mutant_sequence": mut_seq,
        "position": pos, "wt_aa": seq[pos - 1], "mutant_aa": mut_aa,
        "model": svc.model_name, "wt_from_cache": wt_cached,
        "rmsd": rmsd.model_dump(),
        "summary": make_summary(rmsd, seq[pos - 1], pos, mut_aa),
        "plddt_wt_list": [float(x) for x in wt.plddt],
        "plddt_mut_list": [float(x) for x in mut.plddt],
        "pdb_files": ["wt.pdb", "mut.pdb", "mut_aligned.pdb"],
    }


# -- saturation scan: all 19 substitutions at one position --------------------
@router.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest) -> ScanResponse:
    seq = req.sequence
    wt_aa = seq[req.position - 1]
    targets = [aa for aa in AA_ALPHABET if aa != wt_aa]
    job_id = _jm().submit(
        kind="scan",
        params={"sequence": seq, "position": req.position,
                "targets": targets, "profile": req.profile},
        run_fn=_run_scan,
        use_gpu=bool(req.profile) or _gpu_needed())
    return ScanResponse(job_id=job_id, status="queued",
                        length=len(seq))


def _run_scan(job: Job) -> dict:
    """Fold WT once, then all 19 substitutions; rank by local RMSD.

    This is the workload the batched CUDA Kabsch kernel exists for: each
    mutant alignment is one pair — the real screening use case.
    """
    settings = get_settings()
    svc = get_folding_service()
    jm = _jm()
    seq: str = job.params["sequence"]
    pos: int = job.params["position"]
    targets: list[str] = job.params["targets"]
    wt_aa = seq[pos - 1]

    _stage(job, jm, "подготовка модели", 0.02)
    _prepare_model(job, svc)
    _ = svc.model
    if svc.cache.get(seq, svc.model_name) is None:
        _stage(job, jm, "инференс WT", 0.05)
    wt, wt_cached = svc.predict_cached(seq)
    wt_ca = wt.coords_ca

    rows = []
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(wt.pdb_text)
    best = None  # (local_rmsd, mut_aa)
    from ..services.align_service import write_aligned_pdb
    import hpc_core

    n = len(targets)
    for i, mut_aa in enumerate(targets):
        mut = svc.model.predict(mutant_sequence(seq, pos, mut_aa))
        _stage(job, jm, f"мутант {wt_aa}{pos}{mut_aa} ({i + 1}/{n})",
               0.1 + 0.8 * (i + 1) / n)
        al = align_pair(wt_ca, mut.coords_ca, position=pos,
                        radius=settings.local_radius)
        rows.append({
            "mut_aa": mut_aa,
            "local_rmsd": al.local_rmsd, "global_rmsd": al.global_rmsd,
            "tm_score": al.tm_score, "plddt_mut": mut.plddt_mean,
            "dplddt": float(mut.plddt_mean - wt.plddt_mean),
            "engine": al.engine,
            "interpretation": interpret_rmsd(
                al.local_rmsd, settings.rmsd_stable_below,
                settings.rmsd_critical_above),
        })
        # keep only the strongest mutant's aligned PDB (viewer artifact)
        if rows[i]["local_rmsd"] > max((r["local_rmsd"] for r in rows[:-1]), default=-1):
            full = hpc_core.kabsch(mut.coords_ca, wt_ca)
            (out_dir / f"scan_{mut_aa}.pdb").write_text(
                write_aligned_pdb(mut.pdb_text, full.R, full.t))
            for stale in list(out_dir.glob("scan_*.pdb")):
                if stale.name != f"scan_{mut_aa}.pdb":
                    stale.unlink()

    rows.sort(key=lambda r: r["local_rmsd"], reverse=True)
    best_aa, best = rows[0]["mut_aa"], rows[0]
    worst = rows[-1]
    summary = (f"Скан позиции {pos}: {n} замен вокруг {wt_aa}. "
               f"Сильнейший отклик — {wt_aa}{pos}{best_aa} "
               f"(local RMSD {best['local_rmsd']:.2f} Å), "
               f"нейтральнейший — {wt_aa}{pos}{worst['mut_aa']} "
               f"({worst['local_rmsd']:.2f} Å). "
               f"Разброс ×{best['local_rmsd'] / max(worst['local_rmsd'], 1e-9):.1f} — "
               "порядок откликов и есть предиктивный сигнал на детерминированной модели.")
    return {
        "wt_sequence": seq, "position": pos, "wt_aa": wt_aa,
        "model": svc.model_name, "wt_from_cache": wt_cached,
        "rows": rows,
        "plddt_wt": wt.plddt_mean,
        "best": best_aa,
        "summary": summary,
        "pdb_files": ["wt.pdb", f"scan_{best_aa}.pdb"],
    }