"""Predict + mutate endpoints (jobs)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ml.folding.base import mutant_sequence  # noqa: E402
from ..schemas import (  # noqa: E402
    MutationResult, PredictRequest, PredictResponse, RmsdResult, MutateRequest,
    interpret_rmsd,
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


def _run_predict(job: Job) -> dict:
    svc = get_folding_service()
    jm = _jm()
    seq = job.params["sequence"]
    _stage(job, jm, "загрузка модели", 0.05)
    _ = svc.model  # force weight load under the "загрузка" message
    res, from_cache = svc.predict_cached(seq)
    _stage(job, jm, "сохранение PDB", 0.9)
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(res.pdb_text)
    return {
        "length": len(seq), "model": svc.model_name, "from_cache": from_cache,
        "plddt_mean": res.plddt_mean,
        "pdb_file": "wt.pdb",
    }


def _jm():
    return get_job_manager()


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    jm = _jm()
    job_id = jm.submit(
        kind="predict", params={"sequence": req.sequence},
        run_fn=_run_predict, use_gpu=_gpu_needed(req.sequence))
    return PredictResponse(job_id=job_id, status="queued",
                           length=len(req.sequence))


def _gpu_needed(seq: str) -> bool:
    """Real model on CUDA → GPU slot; dummy model → CPU pool."""
    svc = get_folding_service()
    return "omegafold" in svc.model_name


@router.post("/mutate", response_model=MutationResult)
def mutate(req: MutateRequest) -> MutationResult:
    seq = req.sequence
    if seq[req.position - 1] == req.mutant_aa:
        raise HTTPException(422, "mutant residue equals WT residue at that position")
    jm = _jm()
    job_id = jm.submit(
        kind="mutate",
        params={"sequence": seq, "position": req.position,
                "mutant_aa": req.mutant_aa},
        run_fn=_run_mutate, use_gpu=_gpu_needed(seq))
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
    return {
        "wt_sequence": seq, "mutant_sequence": mut_seq,
        "position": pos, "wt_aa": seq[pos - 1], "mutant_aa": mut_aa,
        "model": svc.model_name, "wt_from_cache": wt_cached,
        "rmsd": rmsd.model_dump(),
        "pdb_files": ["wt.pdb", "mut.pdb", "mut_aligned.pdb"],
    }