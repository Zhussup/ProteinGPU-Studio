"""DMS-validation endpoints: correlate our predictors with ProteinGym fitness.

Protocol (one bounded job, pre-registered in the diploma plan):
  dms_load  — curated assay, singles only, per-row hygiene counters
  dms_map   — DMS numbering → our positions (substring, else global alignment);
              rows the mapping cannot vouch for drop with counters
  dms_plm   — ONE OmegaPLM forward; every mapped row gets its log margin
  dms_folds — bounded folding: WT + top-1-per-PLM-fragile-position + a
              fitness-stratified sample (seeded). The fold plan is driven by
              the PLM prediction, never by fitness — no label leak.
  dms_stats — pre-registered correlations, each with n, bootstrap CI and the
              sign the physics should give (expected_sign)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ml.folding.plm_scoring import get_plm_scorer  # noqa: E402
from ..schemas import DmsValidationInput, DmsValidationResponse  # noqa: E402
from ..config import get_settings  # noqa: E402
from ..services.align_service import align_pair  # noqa: E402
from ..services.dms_service import (  # noqa: E402
    DmsDataError, DmsVariant, assay_by_id, assay_file, list_assays,
    load_assay, map_positions, pick_top1_per_position, stratified_sample,
    zscore,
)
from ..services.folding_service import get_folding_service  # noqa: E402
from ..services.job_manager import Job, get_job_manager  # noqa: E402
from ..services.mutagenesis import grantham  # noqa: E402
from ..services.sensitivity import percentile_rank  # noqa: E402
from ..services.stats_lite import (  # noqa: E402
    spearman, spearman_ci, stride_downsample,
)
from ..services.strings import CAVEATS, norm_lang, stage_text  # noqa: E402
from ..services.summary import make_dms_validation_summary  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["validation"])

# "…_Tsuboyama_2023_2GP8" → автор-год/год/PDB для мета-строки фронта
DMS_ID_PARTS = re.compile(r"^(.+?)_([12]\d{3})_([A-Za-z0-9]+)$")


def _lang(job: Job) -> str:
    return norm_lang(job.params.get("lang"))


def _stage(job: Job, jm, message: str, progress: float) -> None:
    job.message = message
    job.progress = progress
    jm.update(job)


def _jm():
    return get_job_manager()


def _corr(name: str, xs, ys, expected_sign: str) -> dict:
    """{name, spearman|None, n, bootstrap CI, expected_sign} — pre-registered."""
    rho = spearman(xs, ys)
    ci = spearman_ci(xs, ys) if rho is not None else None
    return {
        "name": name, "spearman": rho, "n": len(xs), "ci": ci,
        "expected_sign": expected_sign,
    }


@router.get("/validate/assays")
def validate_assays() -> dict:
    """Curated assay list (pure file I/O, no GPU)."""
    try:
        assays = list_assays()
    except DmsDataError as e:
        raise HTTPException(409, str(e))
    return {"assays": assays}


@router.post("/validate/dms", response_model=DmsValidationResponse)
def validate_dms(req: DmsValidationInput, lang: str = "ru") -> DmsValidationResponse:
    """Sync preflight (assay in curated.json + numbering maps onto the user's
    sequence), then submit the bounded dms_validation job."""
    try:
        a = assay_by_id(req.assay_id)
    except DmsDataError as e:
        raise HTTPException(404, str(e))
    if not assay_file(a).exists():
        raise HTTPException(409, f"assay CSV missing on disk: {a['file']} "
                                 f"(run scripts/30_download_proteingym.py)")
    seq = req.sequence
    target = a["consensus_seq"]
    if len(seq) < len(target) // 2:
        raise HTTPException(422, f"sequence of {len(seq)} aa is far shorter "
                                 f"than the assay target ({len(target)} aa)")
    try:
        _, mapping = map_positions(target, seq)
    except ValueError as e:
        raise HTTPException(422,
                            f"numbering cannot be mapped: {e}. Paste the assay's "
                            f"target protein (or a ≥90%-identical homolog).")
    if len(mapping) < min(8, len(target)):
        raise HTTPException(422, f"only {len(mapping)} of {len(target)} target "
                                 f"positions map onto your sequence — wrong protein?")
    job_id = _jm().submit(
        kind="dms_validation",
        params={"sequence": seq, "assay_id": req.assay_id,
                "sample_n": req.sample_n,
                "fold_positions_max": req.fold_positions_max,
                "seed": req.seed, "profile": req.profile,
                "lang": norm_lang(lang)},
        run_fn=_run_dms_validation,
        use_gpu=bool(req.profile) or "omegafold" in get_folding_service().model_name)
    return DmsValidationResponse(job_id=job_id, status="queued",
                                 length=len(seq), assay_id=req.assay_id)


def _run_dms_validation(job: Job) -> dict:
    svc = get_folding_service()
    jm = _jm()
    lang = _lang(job)
    seq: str = job.params["sequence"]
    assay_id: str = job.params["assay_id"]
    sample_n: int = job.params["sample_n"]
    fold_positions_max: int = job.params["fold_positions_max"]
    seed: int = job.params["seed"]
    caveats: list[dict] = []

    _stage(job, jm, stage_text("model", lang), 0.01)
    from ..routers.predict import _prepare_model  # тот же профиль, та же семантика
    _prepare_model(job, svc)
    _ = svc.model

    # -- dms_load ---------------------------------------------------------
    _stage(job, jm, stage_text("dms_load", lang, id=assay_id), 0.02)
    singles, counts, target = load_assay(assay_id)
    if not singles:
        raise RuntimeError(f"{assay_id}: no single-substitution rows")
    if counts["rows_multi"] > 0:
        caveats.append({"key": "multiFiltered", "params": {"n": counts["rows_multi"]}})

    # -- dms_map ----------------------------------------------------------
    _stage(job, jm, stage_text("dms_map", lang, n=len(target)), 0.08)
    mode, mapping = map_positions(target, seq)
    if mode != "exact-substring":
        caveats.append({"key": "regionMap", "params": {"mode": mode}})
    variants: list[DmsVariant] = []
    for pos, wt_aa, alt_aa, raw in singles:
        pos0 = mapping.get(pos)
        if pos0 is None:
            counts["rows_unmapped"] += 1
            continue
        if seq[pos0] != wt_aa:
            counts["rows_wt_mismatch_local"] += 1
            continue
        variants.append(DmsVariant(
            pos_dms=pos, pos0_local=pos0, wt_aa=wt_aa, alt_aa=alt_aa,
            mut_seq=seq[:pos0] + alt_aa + seq[pos0 + 1:], fitness_raw=raw))
    if len(variants) < 8:
        raise RuntimeError(f"{assay_id}: only {len(variants)} of {len(singles)} "
                           f"singles mapped onto your sequence — wrong protein?")

    # -- dms_plm ----------------------------------------------------------
    _stage(job, jm, stage_text("dms_plm", lang, n=len(variants)), 0.18)
    scorer = get_plm_scorer(svc.model)
    score = scorer.score(seq)
    _stage(job, jm, stage_text("dms_plm", lang, n=len(variants)), 0.24)
    for v in variants:
        v.plm_margin = score.margin(v.pos0_local, v.alt_aa)

    # дубликаты (pos, alt) → среднее fitness, счётчик | 重复 → 均值 + 计数
    seen: dict[tuple[int, str], DmsVariant] = {}
    uniq: list[DmsVariant] = []
    for v in variants:
        key = (v.pos0_local, v.alt_aa)
        if key in seen:
            first = seen[key]
            first.fitness_raw = (first.fitness_raw * first.count
                                 + v.fitness_raw) / (first.count + 1)
            first.count += 1
            counts["rows_dup_merged"] += 1
        else:
            seen[key] = v
            uniq.append(v)
    variants = uniq
    zs, mu, sd = zscore([v.fitness_raw for v in variants])
    for v, z in zip(variants, zs):
        v.fitness_z = z
    if sd < 1e-9:
        caveats.append({"key": "tiedFitness", "params": {}})

    # позиционная хрупкость PLM: медиана damage по позиции (rank-канал фронта);
    # тот же percentile_rank, ties-at-bottom — байтовый контракт фронта
    by_pos: dict[int, list[DmsVariant]] = {}
    for v in variants:
        by_pos.setdefault(v.pos0_local, []).append(v)
    pool = [float(-sorted(v.plm_margin for v in vs)[len(vs) // 2])
            for vs in by_pos.values()]
    pctl_fragile: dict[int, float] = {}
    for p0, vs in by_pos.items():
        med = sorted(v.plm_margin for v in vs)[len(vs) // 2]
        pctl_fragile[p0] = percentile_rank(-med, pool)

    # zero-shot заголовок: margin vs fitness по ВСЕМ mapped singles
    plm_all = _corr("plm_all",
                    [v.plm_margin for v in variants],
                    [v.fitness_z for v in variants], "+")

    # -- dms_folds --------------------------------------------------------
    settings = get_settings()
    folded_any = False
    if fold_positions_max > 0 or sample_n > 0:
        # план: top-1 на позицию по НИЗШЕМУ margin (PLM решает, не fitness) +
        # стратифицированная по fitness выборка (экспериментальные хвосты);
        # оба источника капнут ручками — джоба ограничена по construction
        fold_plan = list(pick_top1_per_position(variants, pctl_fragile,
                                                fold_positions_max))
        picked = {id(v) for _, v in fold_plan}
        for v in stratified_sample(variants, sample_n, seed):
            if id(v) not in picked:
                picked.add(id(v))
                fold_plan.append((f"{v.wt_aa}{v.pos0_local + 1}{v.alt_aa}", v))
        n = len(fold_plan)
        _stage(job, jm, stage_text("dms_folds", lang, n=n), 0.3)
        if svc.cache.get(seq, svc.model_name) is None:
            _stage(job, jm, stage_text("wt", lang), 0.32)
        wt, wt_cached = svc.predict_cached(seq)
        (jm.job_dir(job.job_id) / "wt.pdb").write_text(wt.pdb_text)
        for i, (label, v) in enumerate(fold_plan):
            mut = svc.model.predict(v.mut_seq)
            _stage(job, jm, stage_text("dms_fold_one", lang, m=label,
                                       i=i + 1, n=n),
                   0.3 + 0.6 * (i + 1) / max(1, n))
            al = align_pair(wt.coords_ca, mut.coords_ca,
                            position=v.pos0_local + 1, radius=settings.local_radius)
            a, b = al.local_window  # 1-based, включительно
            v.dplddt_local = float(sum(
                mut.plddt[j] - wt.plddt[j] for j in range(a - 1, b)) / (b - a + 1))
            v.local_rmsd = al.local_rmsd
            v.dplddt = float(mut.plddt_mean - wt.plddt_mean)
            v.plddt_mut = mut.plddt_mean
            v.engine = al.engine
        folded_any = n > 0
    else:
        wt = None
        wt_cached = None  # PLM-only прогон: wt.pdb не пишем

    # -- dms_stats --------------------------------------------------------
    _stage(job, jm, stage_text("dms_stats", lang, n=len(variants)), 0.96)
    folded = [v for v in variants if v.local_rmsd is not None]

    # per-position агрегат: роза (v_med/pctl) против среднего эксперимента
    per_position = []
    for p0 in sorted(by_pos):
        vs = by_pos[p0]
        top1 = min(vs, key=lambda v: v.plm_margin)
        per_position.append({
            "pos": p0 + 1, "wt_aa": seq[p0],
            "v_med": float(-sorted(v.plm_margin for v in vs)[len(vs) // 2]),
            "v_med_pctl": pctl_fragile[p0],
            "mean_fitness_z": round(
                sum(v.fitness_z for v in vs) / len(vs), 4),
            "n_obs": len(vs),
            "top1": {"mut_aa": top1.alt_aa, "local_rmsd": top1.local_rmsd,
                     "fitness_z": round(top1.fitness_z, 4)}
            if top1.local_rmsd is not None else None,
        })

    correlations = [
        plm_all,
        _corr("plddt_fold",
              [v.dplddt for v in folded], [v.fitness_z for v in folded], "-"),
        _corr("rmsd_fold",
              [v.local_rmsd for v in folded], [v.fitness_z for v in folded], "-"),
        # per-position уровень: медиана damage позиции против среднего fitness
        _corr("pos_plm",
              [pp["v_med"] for pp in per_position],
              [pp["mean_fitness_z"] for pp in per_position], "-"),
        # согласие PLM↔структура: топ-1 (по PLM) с его локальным RMSD
        _corr("pos_struct_plm",
              [pp["top1"]["local_rmsd"] for pp in per_position
               if pp["top1"] is not None],
              [pp["v_med"] for pp in per_position if pp["top1"] is not None], "+"),
        _corr("margin_rmsd",
              [v.plm_margin for v in folded], [v.local_rmsd for v in folded], "-"),
    ]

    if len(folded) < min(40, len(variants)):
        caveats.append({"key": "foldSubset",
                        "params": {"folded": len(folded), "total": len(variants)}})
    caveats.append({"key": "zscoreCenter", "params": {}})
    if scorer.name == "dummy-plm":
        caveats.append({"key": "dummyProfile", "params": {}})

    # -- артефакты (все mapped singles; структурные колонки у не-фолднутых пустые)
    def vp(v: DmsVariant) -> dict:
        return {
            "pos_dms": v.pos_dms, "pos": v.pos0_local + 1,
            "wt_aa": v.wt_aa, "mut_aa": v.alt_aa,
            "fitness": round(v.fitness_raw, 6),
            "fitness_z": round(v.fitness_z, 4),
            "plm_margin": round(v.plm_margin, 6),
            "count": v.count,
            "local_rmsd": round(v.local_rmsd, 6) if v.local_rmsd is not None else None,
            "dplddt": round(v.dplddt, 6) if v.dplddt is not None else None,
            "dplddt_local": round(v.dplddt_local, 6)
            if v.dplddt_local is not None else None,
            "folded": v.local_rmsd is not None,
        }

    all_rows = [vp(v) for v in variants]
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "dms_validation.json").write_text(json.dumps(
        {"assay_id": assay_id, "sequence": seq, "model": svc.model_name,
         "mapping": mode, "counts": counts, "n_rows": len(variants),
         "assay_center": {"mu": round(mu, 4), "sd": round(sd, 4)},
         "correlations": correlations, "per_position": per_position,
         "caveats": caveats, "rows": all_rows},
        ensure_ascii=False))
    header = ("pos_dms,pos,wt_aa,mut_aa,fitness,fitness_z,plm_margin,"
              "grantham,local_rmsd,dplddt,dplddt_local,folded")
    lines = [header]
    for r in all_rows:
        lines.append(",".join([
            str(r["pos_dms"]), str(r["pos"]), r["wt_aa"], r["mut_aa"],
            f"{r['fitness']:.6f}", f"{r['fitness_z']:.4f}",
            f"{r['plm_margin']:.6f}", str(grantham(r["wt_aa"], r["mut_aa"])),
            "" if r["local_rmsd"] is None else f"{r['local_rmsd']:.6f}",
            "" if r["dplddt"] is None else f"{r['dplddt']:+.4f}",
            "" if r["dplddt_local"] is None else f"{r['dplddt_local']:+.4f}",
            "1" if r["folded"] else "0",
        ]))
    (out_dir / "dms_validation.csv").write_text("\n".join(lines) + "\n")

    corr_by_name = {c["name"]: c for c in correlations}
    summary = make_dms_validation_summary(
        assay_id=assay_id, n_rows=len(variants),
        plm_rho=corr_by_name["plm_all"]["spearman"],
        n_plm=corr_by_name["plm_all"]["n"],
        dplddt_rho=corr_by_name["plddt_fold"]["spearman"],
        n_fold=corr_by_name["plddt_fold"]["n"], lang=lang)

    parts = DMS_ID_PARTS.match(assay_id)
    dms_meta = {
        "seq_len": len(target),
        "author_year": f"{parts.group(1).split('_')[-1]} {parts.group(2)}"
        if parts else assay_id,
        "year": parts.group(2) if parts else "",
    }

    return {
        "kind": "dms_validation",
        "assay_id": assay_id, "dms_meta": dms_meta,
        "sequence": seq, "model": svc.model_name,
        "plm_scorer": scorer.name, "mapping": mode,
        "counts": counts, "n_rows": len(variants),
        "assay_center": {"mu": round(mu, 4), "sd": round(sd, 4)},
        "correlations": correlations,
        "per_position": per_position,
        "scatter_plm": [{"x": round(v.plm_margin, 4), "y": round(v.fitness_z, 4),
                         "label": f"{v.wt_aa}{v.pos0_local + 1}{v.alt_aa}"}
                        for v in stride_downsample(variants, 800)],
        "scatter_struct": [{"x": round(v.local_rmsd, 4),
                            "y": round(v.fitness_z, 4),
                            "label": f"{v.wt_aa}{v.pos0_local + 1}{v.alt_aa}"}
                           for v in stride_downsample(folded, 800)],
        "caveats": caveats, "summary": summary,
        "wt_from_cache": wt_cached,
        "pdb_files": ["wt.pdb"] if folded_any else [],
        "artifact_files": ["dms_validation.json", "dms_validation.csv"],
        "n_positions": len(per_position),
    }