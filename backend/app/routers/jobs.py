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


def _retranslated_summary(res: dict, lang: str) -> dict:
    """Return the result dict with `summary` regenerated in `lang`.

    The summary is a pure function of the stored metrics (no re-folding), so
    history restores in whatever UI language is active right now. Falls back
    to the stored text for results it cannot regenerate.
    """
    from ..services.summary import (make_ensemble_summary, make_scan_summary,
                                    make_summary)
    try:
        out = dict(res)
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
                # exhaustive is the scan workload — the scan sentence keeps
                # byte parity with /scan (lossless-migration requirement)
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
    # no ?lang= → the summary as generated at submit time; an explicit lang
    # retranslates it to the UI language active right now
    if lang is None:
        return job.result
    return _retranslated_summary(job.result, norm_lang(lang))


@router.get("/files/{job_id}/{fn}", response_class=PlainTextResponse)
def job_file(job_id: str, fn: str) -> PlainTextResponse:
    _job_or_404(job_id)
    is_scan_artifact = fn.startswith("scan_") and fn.endswith(".pdb") and len(fn) == 10
    is_ens_artifact = fn.startswith("ens_") and fn.endswith(".pdb") and len(fn) == 10
    if fn not in {"wt.pdb", "mut.pdb", "mut_aligned.pdb"} and not (
            is_scan_artifact or is_ens_artifact):
        raise HTTPException(404, "unknown artifact")
    path = get_job_manager().job_dir(job_id) / fn
    if not path.exists():
        raise HTTPException(404, f"artifact {fn} not written yet")
    return PlainTextResponse(path.read_text(), media_type="chemical/x-pdb")