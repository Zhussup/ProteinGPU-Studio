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
    EnsembleRequest, EnsembleResponse,
    ScanMapRequest, ScanMapResponse,
)
from ..config import get_settings  # noqa: E402
from ..services.align_service import align_pair  # noqa: E402
from ..services.folding_service import get_folding_service  # noqa: E402
from ..services.job_manager import Job, get_job_manager  # noqa: E402
from ..services.mutagenesis import (  # noqa: E402
    apply_mutations, derived_seed, distribution_stats, exhaustive_mutations,
    grantham, mutation_label, sample_variants, sensitivity_headline,
)
from ..services.pdb_io import parse_ca_coords  # noqa: E402
from ..services.sensitivity import (  # noqa: E402
    PETAL_DIRS, SECTOR_OF, build_csv, most_fragile, normalize_protein,
    petal_dirs, position_stats, quadrant_counts,
)
from ..services.strings import VALIDATION, norm_lang, stage_text  # noqa: E402

router = APIRouter(prefix="/api/v1", tags=["folding"])


def _lang(job: Job) -> str:
    """UI language the job was submitted with (stage messages, summaries)."""
    return norm_lang(job.params.get("lang"))


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
    lang = _lang(job)
    seq = job.params["sequence"]
    _stage(job, jm, stage_text("model", lang), 0.03)
    _prepare_model(job, svc)
    _ = svc.model  # форсируем загрузку весов под сообщением этапа "model" | 在 "model" 阶段消息下强制加载权重
    _stage(job, jm, stage_text("wt", lang), 0.1)
    res, from_cache = svc.predict_cached(seq)
    _stage(job, jm, stage_text("pdb", lang), 0.9)
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(res.pdb_text)
    return {
        "length": len(seq), "model": svc.model_name, "from_cache": from_cache,
        "plddt_mean": res.plddt_mean,
        "plddt_list": [float(x) for x in res.plddt],
        "pdb_file": "wt.pdb",
    }


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, lang: str = "ru") -> PredictResponse:
    job_id = _jm().submit(
        kind="predict", params={"sequence": req.sequence, "profile": req.profile,
                                "lang": norm_lang(lang)},
        run_fn=_run_predict,
        use_gpu=bool(req.profile) or _gpu_needed())
    return PredictResponse(job_id=job_id, status="queued",
                           length=len(req.sequence))


def _gpu_needed() -> bool:
    """A resident real model must be serialized even for the cpu profile —
    it is the same singleton object. Dummy-model tests stay on the CPU pool."""
    return "omegafold" in get_folding_service().model_name


@router.post("/mutate", response_model=MutationResult)
def mutate(req: MutateRequest, lang: str = "ru") -> MutationResult:
    seq = req.sequence
    if seq[req.position - 1] == req.mutant_aa:
        raise HTTPException(422, VALIDATION[norm_lang(lang)]["same_residue"])
    job_id = _jm().submit(
        kind="mutate",
        params={"sequence": seq, "position": req.position,
                "mutant_aa": req.mutant_aa, "profile": req.profile,
                "lang": norm_lang(lang)},
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
    lang = _lang(job)
    seq: str = job.params["sequence"]
    pos: int = job.params["position"]
    mut_aa: str = job.params["mutant_aa"]
    mut_seq = mutant_sequence(seq, pos, mut_aa)

    _stage(job, jm, stage_text("model", lang), 0.03)
    _prepare_model(job, svc)
    _ = svc.model  # форсируем загрузку весов под сообщением этапа "model" | 在 "model" 阶段消息下强制加载权重
    if svc.cache.get(seq, svc.model_name) is None:
        _stage(job, jm, stage_text("wt", lang), 0.1)  # пропускается при попадании в кэш | 缓存命中时跳过
    wt, wt_cached = svc.predict_cached(seq)
    _stage(job, jm, stage_text("mutant", lang), 0.5)
    mut = svc.model.predict(mut_seq)
    _stage(job, jm, stage_text("pdbs", lang), 0.8)

    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(wt.pdb_text)
    (out_dir / "mut.pdb").write_text(mut.pdb_text)

    # Выравниваем мутанта НА WT в системе координат WT; пишем пре-выровненный PDB.
    # 将突变体对齐到 WT 坐标系；写出预对齐的突变体 PDB。
    _stage(job, jm, stage_text("kabsch", lang), 0.85)
    al = align_pair(parse_ca_coords(wt.pdb_text), parse_ca_coords(mut.pdb_text),
                    position=pos, radius=settings.local_radius)
    from ..services.align_service import write_aligned_pdb
    import hpc_core
    full = hpc_core.kabsch(mut.coords_ca, wt.coords_ca)
    (out_dir / "mut_aligned.pdb").write_text(
        write_aligned_pdb(mut.pdb_text, full.R, full.t))

    _stage(job, jm, stage_text("metrics", lang), 0.95)
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
        "summary": make_summary(rmsd, seq[pos - 1], pos, mut_aa, lang),
        "plddt_wt_list": [float(x) for x in wt.plddt],
        "plddt_mut_list": [float(x) for x in mut.plddt],
        "pdb_files": ["wt.pdb", "mut.pdb", "mut_aligned.pdb"],
    }


# -- скан насыщения: все 19 замен в одной позиции ------------------------------
# -- 饱和扫描：单一位点上的全部 19 种替换 ----------------------------------------
@router.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest, lang: str = "ru") -> ScanResponse:
    seq = req.sequence
    wt_aa = seq[req.position - 1]
    targets = [aa for aa in AA_ALPHABET if aa != wt_aa]
    job_id = _jm().submit(
        kind="scan",
        params={"sequence": seq, "position": req.position,
                "targets": targets, "profile": req.profile,
                "lang": norm_lang(lang)},
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
    lang = _lang(job)
    seq: str = job.params["sequence"]
    pos: int = job.params["position"]
    targets: list[str] = job.params["targets"]
    wt_aa = seq[pos - 1]

    _stage(job, jm, stage_text("model", lang), 0.02)
    _prepare_model(job, svc)
    _ = svc.model
    if svc.cache.get(seq, svc.model_name) is None:
        _stage(job, jm, stage_text("wt", lang), 0.05)
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
        _stage(job, jm, stage_text("subs", lang, m=f"{wt_aa}{pos}{mut_aa}",
                                   i=i + 1, n=n),
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
        # храним выровненный PDB только самого сильного мутанта (артефакт для вьюера)
        # 仅保留最强突变体的对齐 PDB（查看器工件）
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
    from ..services.summary import make_scan_summary
    summary = make_scan_summary(
        pos, n, wt_aa,
        best_aa=best_aa, best_rmsd=best["local_rmsd"],
        worst_aa=worst["mut_aa"], worst_rmsd=worst["local_rmsd"],
        lang=lang)
    return {
        "wt_sequence": seq, "position": pos, "wt_aa": wt_aa,
        "model": svc.model_name, "wt_from_cache": wt_cached,
        "rows": rows,
        "plddt_wt": wt.plddt_mean,
        "best": best_aa,
        "summary": summary,
        "pdb_files": ["wt.pdb", f"scan_{best_aa}.pdb"],
    }


# -- ансамбль силы мутагенеза: K вариантов, сэмплированных по (mu, tau) --------
# -- 诱变强度集成：按 (mu, tau) 采样 K 个变体 ------------------------------------
@router.post("/ensemble", response_model=EnsembleResponse)
def ensemble(req: EnsembleRequest, lang: str = "ru") -> EnsembleResponse:
    """The strength dial's run: sample K variants (anchor + background
    substitutions weighted by the Grantham spectrum) and measure the anchor
    position's sensitivity as the distribution of responses. mode="exhaustive"
    folds all 19 substitutions — the /scan workload, kept for migration."""
    seq = req.sequence
    seed_eff = req.seed if req.seed is not None else derived_seed(
        seq, req.position, req.mu, req.tau, req.k)
    job_id = _jm().submit(
        kind="ensemble",
        params={"sequence": seq, "position": req.position, "mode": req.mode,
                "mu": req.mu, "tau": req.tau, "k": req.k, "seed": req.seed,
                "effective_seed": seed_eff, "profile": req.profile,
                "lang": norm_lang(lang)},
        run_fn=_run_ensemble,
        use_gpu=bool(req.profile) or _gpu_needed())
    return EnsembleResponse(
        job_id=job_id, status="queued", length=len(seq),
        wt_aa=seq[req.position - 1], mode=req.mode,
        mu=req.mu, tau=req.tau, k=req.k)


def _run_ensemble(job: Job) -> dict:
    """Fold WT once, then each sampled variant; the anchor's sensitivity is
    the distribution (median/IQR/spread) of the per-variant responses.

    Mirrors _run_scan: one job, sequential folds with per-variant stage
    progress, strongest-first ranking, aligned-PDB artifacts. mode="exhaustive"
    reproduces the scan exactly (same target order, same summary sentence).
    """
    settings = get_settings()
    svc = get_folding_service()
    jm = _jm()
    lang = _lang(job)
    seq: str = job.params["sequence"]
    pos: int = job.params["position"]
    mode: str = job.params["mode"]
    mu: int = job.params["mu"]
    tau: float = job.params["tau"]
    k: int = job.params["k"]
    seed: int = job.params["effective_seed"]
    wt_aa = seq[pos - 1]

    _stage(job, jm, stage_text("model", lang), 0.02)
    _prepare_model(job, svc)
    _ = svc.model
    if svc.cache.get(seq, svc.model_name) is None:
        _stage(job, jm, stage_text("wt", lang), 0.05)
    wt, wt_cached = svc.predict_cached(seq)
    wt_ca = wt.coords_ca
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(wt.pdb_text)

    if mode == "exhaustive":
        muts_list = exhaustive_mutations(seq, pos)
    else:
        muts_list = sample_variants(seq, pos, mu, tau, k, seed)
    n = len(muts_list)

    from ..services.align_service import write_aligned_pdb
    import hpc_core

    rows = []
    # аккумулятор |ΔpLDDT| по остаткам (дорожка для вьюера)
    # 逐残基 |ΔpLDDT| 累加器（查看器轨道）
    abs_sum = [0.0] * len(seq)
    for i, muts in enumerate(muts_list):
        mut = svc.model.predict(apply_mutations(seq, muts))
        label = mutation_label(muts)
        _stage(job, jm, stage_text("ens", lang, m=label, i=i + 1, n=n),
               0.1 + 0.8 * (i + 1) / n)
        al = align_pair(wt_ca, mut.coords_ca, position=pos,
                        radius=settings.local_radius)
        a, b = al.local_window  # с 1, включительно | 从 1 开始、含端点
        dplddt_local = float(sum(
            mut.plddt[j] - wt.plddt[j] for j in range(a - 1, b)) / (b - a + 1))
        for j in range(len(seq)):
            abs_sum[j] += abs(mut.plddt[j] - wt.plddt[j])
        rows.append({
            "label": label,
            "mutations": [{"position": p, "wt_aa": w, "mut_aa": m}
                          for p, w, m in muts],
            "mut_aa": muts[0][2] if len(muts) == 1 else None,
            "local_rmsd": al.local_rmsd, "global_rmsd": al.global_rmsd,
            "tm_score": al.tm_score, "plddt_mut": mut.plddt_mean,
            "dplddt": float(mut.plddt_mean - wt.plddt_mean),
            "dplddt_local": dplddt_local,
            "engine": al.engine,
            "interpretation": interpret_rmsd(
                al.local_rmsd, settings.rmsd_stable_below,
                settings.rmsd_critical_above),
            # не попадает в сохраняемую строку (удаляется до сборки result-словаря)
            # 不写入持久化行（在组装结果字典前弹出）
            "_coords": mut.coords_ca, "_pdb_text": mut.pdb_text,
        })

    rows.sort(key=lambda r: r["local_rmsd"], reverse=True)
    for i, r in enumerate(rows):
        full = hpc_core.kabsch(r.pop("_coords"), wt_ca)
        (out_dir / f"ens_{i:02d}.pdb").write_text(
            write_aligned_pdb(r.pop("_pdb_text"), full.R, full.t))
        r["pdb_file"] = f"ens_{i:02d}.pdb"

    stats = {
        "local_rmsd": distribution_stats([r["local_rmsd"] for r in rows]),
        "dplddt": distribution_stats([r["dplddt"] for r in rows]),
        "dplddt_local": distribution_stats([r["dplddt_local"] for r in rows]),
    }
    med_abs = distribution_stats([abs(r["dplddt_local"]) for r in rows])["median"]
    headline = sensitivity_headline(stats["local_rmsd"], med_abs)

    from ..services.summary import make_ensemble_summary, make_scan_summary
    if mode == "exhaustive":
        summary = make_scan_summary(
            pos, n, wt_aa,
            best_aa=rows[0]["mut_aa"], best_rmsd=rows[0]["local_rmsd"],
            worst_aa=rows[-1]["mut_aa"], worst_rmsd=rows[-1]["local_rmsd"],
            lang=lang)
    else:
        summary = make_ensemble_summary(pos, wt_aa, mu, tau, n, stats,
                                        headline, lang)
    return {
        "wt_sequence": seq, "position": pos, "wt_aa": wt_aa,
        "model": svc.model_name, "wt_from_cache": wt_cached, "mode": mode,
        "params": {"mu": mu, "tau": tau, "k": k, "seed": seed},
        "variants": rows,
        "stats": stats, "headline": headline,
        "dplddt_abs_mean_list": [s / n for s in abs_sum],
        "plddt_wt": wt.plddt_mean,
        "plddt_wt_list": [float(x) for x in wt.plddt],
        "best": 0,
        "summary": summary,
        "pdb_files": ["wt.pdb"] + [f"ens_{i:02d}.pdb" for i in range(n)],
    }


# -- карта чувствительности: 19-вектор в каждой позиции (dum.md §5) -------------
# -- 敏感性图谱：每个位点的 19 维向量（dum.md §5）---------------------------------
@router.post("/scan_map", response_model=ScanMapResponse)
def scan_map(req: ScanMapRequest, lang: str = "ru") -> ScanMapResponse:
    """The wind-rose job: fold WT once, then every requested position's 19
    substitutions (all positions by default) — 19*L folds, the honest map.
    A position subset keeps a demo bounded; the full map is the same loop."""
    seq = req.sequence
    positions = req.positions or list(range(1, len(seq) + 1))
    job_id = _jm().submit(
        kind="scan_map",
        params={"sequence": seq, "positions": positions,
                "profile": req.profile, "lang": norm_lang(lang)},
        run_fn=_run_scan_map,
        use_gpu=bool(req.profile) or _gpu_needed())
    return ScanMapResponse(job_id=job_id, status="queued", length=len(seq),
                           n_positions=len(positions),
                           n_folds=19 * len(positions))


def _run_scan_map(job: Job) -> dict:
    """Fold WT once, then each position's 19 substitutions in the fixed compass
    order; the position's sensitivity is its 19-vector (the rose).

    Rows are emitted in rose order (PETAL_DIRS minus the WT slot) so the UI
    draws the glyph straight from the artifact; ranking scalars live in stats.
    One checkpoint per finished position — the GPU-hours survive an error
    (scan_map_partial.json), and the fold cache makes an identical rerun free.
    Mutant PDBs are NOT kept: this is a data job, not a structure job — the
    aligned strongest mutant comes from /scan on demand.
    """
    import json
    settings = get_settings()
    svc = get_folding_service()
    jm = _jm()
    lang = _lang(job)
    seq: str = job.params["sequence"]
    positions: list[int] = job.params["positions"]
    n = len(positions)
    total_folds = 19 * n

    _stage(job, jm, stage_text("model", lang), 0.02)
    _prepare_model(job, svc)
    _ = svc.model
    if svc.cache.get(seq, svc.model_name) is None:
        _stage(job, jm, stage_text("wt", lang), 0.05)
    wt, wt_cached = svc.predict_cached(seq)
    wt_ca = wt.coords_ca
    out_dir = jm.job_dir(job.job_id)
    (out_dir / "wt.pdb").write_text(wt.pdb_text)

    results = []
    for i, pos in enumerate(positions):
        _stage(job, jm, stage_text("map", lang, m=f"{seq[pos - 1]}{pos}",
                                   i=i + 1, n=n),
               0.1 + 0.85 * (i + 1) / n)
        rows = []
        for mut_aa in petal_dirs(seq[pos - 1]):
            mut = svc.model.predict(mutant_sequence(seq, pos, mut_aa))
            al = align_pair(wt_ca, mut.coords_ca, position=pos,
                            radius=settings.local_radius)
            a, b = al.local_window  # с 1, включительно | 从 1 开始、含端点
            dplddt_local = float(sum(
                mut.plddt[j] - wt.plddt[j] for j in range(a - 1, b)) / (b - a + 1))
            rows.append({
                "mut_aa": mut_aa,
                "grantham": grantham(seq[pos - 1], mut_aa),
                "local_rmsd": al.local_rmsd, "global_rmsd": al.global_rmsd,
                "tm_score": al.tm_score, "plddt_mut": mut.plddt_mean,
                "dplddt": float(mut.plddt_mean - wt.plddt_mean),
                "dplddt_local": dplddt_local,
                "abs_dplddt_local": abs(dplddt_local),
                "engine": al.engine,
                "interpretation": interpret_rmsd(
                    al.local_rmsd, settings.rmsd_stable_below,
                    settings.rmsd_critical_above),
            })
        stats = position_stats([r["local_rmsd"] for r in rows],
                               [r["abs_dplddt_local"] for r in rows])
        results.append({"pos": pos, "wt_aa": seq[pos - 1], "rows": rows,
                        "stats": stats})
        # чекпоинт: каждая завершённая позиция уже принадлежит пользователю
        # 检查点：每个已完成位点对用户而言已保存
        (out_dir / "scan_map_partial.json").write_text(json.dumps(
            {"sequence": seq, "done": len(results), "total": n,
             "positions": results}, ensure_ascii=False))

    normalize_protein(results)
    from ..services.summary import make_scan_map_summary
    fragile = most_fragile(results)
    summary = make_scan_map_summary(
        n=n, folds=total_folds + 1, fragile=fragile,
        counts=quadrant_counts(results), lang=lang)

    (out_dir / "scan_map.json").write_text(json.dumps(
        {"sequence": seq, "model": svc.model_name,
         "petal_dirs": PETAL_DIRS, "positions": results},
        ensure_ascii=False))
    (out_dir / "scan_map.csv").write_text(build_csv(results))

    return {
        "wt_sequence": seq, "model": svc.model_name,
        "wt_from_cache": wt_cached,
        "n_positions": n, "n_folds": total_folds + 1,
        "plddt_wt": wt.plddt_mean,
        "plddt_wt_list": [float(x) for x in wt.plddt],
        "petal_dirs": PETAL_DIRS,
        "positions": results,
        "summary": summary,
        "pdb_files": ["wt.pdb"],
        "artifact_files": ["scan_map.json", "scan_map.csv"],
    }