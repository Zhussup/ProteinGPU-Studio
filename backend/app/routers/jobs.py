"""Job status + artifact download endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..schemas import JobStatus, RmsdResult
from ..services.job_manager import get_job_manager
from ..services.strings import norm_lang

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.get("/jobs")
def job_history(limit: int = 50) -> list[dict]:
    """Recent jobs, newest first (history panel)."""
    return get_job_manager().list(limit=min(max(limit, 1), 200))


def _job_or_404(job_id: str):
    job = get_job_manager().get(job_id)
    if job is None:
        raise HTTPException(404, f"job {job_id} not found")
    return job


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    return JobStatus(**_job_or_404(job_id).to_dict())


@router.post("/jobs/{job_id}/cancel", response_model=JobStatus)
def job_cancel(job_id: str) -> JobStatus:
    """Кооперативно остановить джоб и освободить GPU-слот.

    Идемпотентно для уже отменённого (двойной клик по кнопке безопасен);
    завершённый джоб отменять поздно — 409, как у /result без результата.
    协作式停止任务并释放 GPU 槽位。对已取消的任务幂等（重复点击安全）；
    已完成的任务取消太晚——与 /result 无结果时一致，返回 409。
    """
    job = _job_or_404(job_id)
    if job.status in ("done", "error"):
        raise HTTPException(409, f"job {job_id} is {job.status}, cannot cancel")
    if job.status == "cancelled":
        return JobStatus(**job.to_dict())
    cancelled = get_job_manager().cancel(job_id)
    return JobStatus(**cancelled.to_dict())


def _retranslated_summary(res: dict, lang: str) -> dict:
    """Return the result dict with `summary` regenerated in `lang`.

    The summary is a pure function of the stored metrics (no re-folding), so
    history restores in whatever UI language is active right now. Falls back
    to the stored text for results it cannot regenerate.
    """
    from ..services.summary import (make_dms_validation_summary,
                                    make_ensemble_summary, make_plm_screen_summary,
                                    make_scan_map_summary, make_scan_summary,
                                    make_summary)
    from ..services.sensitivity import most_fragile, quadrant_counts
    try:
        out = dict(res)
        kind = res.get("kind")  # дискриминатор ПЕРЕД shape-ветками: PLM-результат
        # тоже содержит positions+petal_dirs, но его сводка — другая
        # 判别字段必须先于形状分支：PLM 结果同样含 positions+petal_dirs
        if kind == "plm_screen":
            frag = most_fragile(res["positions"])
            f = res.get("folds") or {}
            out["summary"] = make_plm_screen_summary(
                n_pos=len(res["positions"]), folds_done=f.get("done", 0),
                fragile=frag, scorer=res.get("plm_scorer", ""), lang=lang)
            return out
        if kind == "dms_validation":
            corr = {c["name"]: c for c in res["correlations"]}
            out["summary"] = make_dms_validation_summary(
                assay_id=res["assay_id"], n_rows=res.get("n_rows", 0),
                plm_rho=corr["plm_all"]["spearman"],
                n_plm=corr["plm_all"]["n"],
                dplddt_rho=corr["plddt_fold"]["spearman"],
                n_fold=corr["plddt_fold"]["n"], lang=lang)
            return out
        if res.get("rmsd") and "wt_aa" in res:
            out["summary"] = make_summary(
                RmsdResult(**res["rmsd"]), res["wt_aa"],
                res["position"], res["mutant_aa"], lang)
        elif res.get("rows") and "wt_aa" in res:
            rows = res["rows"]
            best, worst = rows[0], rows[-1]
            out["summary"] = make_scan_summary(
                res["position"], len(rows), res["wt_aa"],
                best_aa=best["mut_aa"], best_rmsd=best["local_rmsd"],
                worst_aa=worst["mut_aa"], worst_rmsd=worst["local_rmsd"],
                lang=lang)
        elif res.get("variants") and res.get("stats") and "wt_aa" in res:
            if res.get("mode") == "exhaustive":
                # exhaustive — это нагрузка /scan: предложение сводки сохраняет
                # побайтовый паритет с /scan (требование миграции без потерь)
                # exhaustive 即 /scan 工作负载：摘要句与 /scan 保持逐字节一致（无损迁移要求）
                rows = res["variants"]
                best, worst = rows[0], rows[-1]
                out["summary"] = make_scan_summary(
                    res["position"], len(rows), res["wt_aa"],
                    best_aa=best["mut_aa"], best_rmsd=best["local_rmsd"],
                    worst_aa=worst["mut_aa"], worst_rmsd=worst["local_rmsd"],
                    lang=lang)
            else:
                p = res.get("params") or {}
                out["summary"] = make_ensemble_summary(
                    res["position"], res["wt_aa"],
                    p.get("mu", 1), p.get("tau", 0.5), len(res["variants"]),
                    res["stats"], res["headline"], lang=lang)
        elif res.get("positions") and res.get("petal_dirs"):
            frag = most_fragile(res["positions"])
            out["summary"] = make_scan_map_summary(
                n=len(res["positions"]), folds=res.get("n_folds", 0),
                fragile=frag, counts=quadrant_counts(res["positions"]),
                lang=lang)
        return out
    except (KeyError, TypeError, ValueError):
        return res


@router.get("/jobs/{job_id}/result")
def job_result(job_id: str, lang: str | None = None) -> dict:
    job = _job_or_404(job_id)
    if job.status != "done":
        raise HTTPException(409, f"job {job_id} is {job.status}, no result yet")
    if job.result is None:
        return job.result
    # без ?lang= — сводка как на момент постановки задания; явный lang
    # перезаписывает её на текущий активный язык интерфейса
    # 无 ?lang= 时返回提交时生成的摘要；显式 lang 会将其重译为当前界面语言
    if lang is None:
        return job.result
    return _retranslated_summary(job.result, norm_lang(lang))


@router.get("/files/{job_id}/{fn}", response_class=PlainTextResponse)
def job_file(job_id: str, fn: str) -> PlainTextResponse:
    _job_or_404(job_id)
    is_scan_artifact = fn.startswith("scan_") and fn.endswith(".pdb") and len(fn) == 10
    is_ens_artifact = fn.startswith("ens_") and fn.endswith(".pdb") and len(fn) == 10
    is_map_artifact = fn in {"scan_map.json", "scan_map.csv",
                             "scan_map_partial.json"}
    is_plm_artifact = fn in {"plm_screen.json", "plm_screen.csv"}
    is_dms_artifact = fn in {"dms_validation.json", "dms_validation.csv"}
    if fn not in {"wt.pdb", "mut.pdb", "mut_aligned.pdb"} and not (
            is_scan_artifact or is_ens_artifact or is_map_artifact
            or is_plm_artifact or is_dms_artifact):
        raise HTTPException(404, "unknown artifact")
    path = get_job_manager().job_dir(job_id) / fn
    if not path.exists():
        raise HTTPException(404, f"artifact {fn} not written yet")
    media_type = "chemical/x-pdb" if fn.endswith(".pdb") else "text/plain"
    return PlainTextResponse(path.read_text(), media_type=media_type)