"""Job status + artifact download endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..schemas import JobStatus
from ..services.job_manager import get_job_manager

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def _job_or_404(job_id: str):
    job = get_job_manager().get(job_id)
    if job is None:
        raise HTTPException(404, f"job {job_id} not found")
    return job


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    return JobStatus(**_job_or_404(job_id).to_dict())


@router.get("/jobs/{job_id}/result")
def job_result(job_id: str) -> dict:
    job = _job_or_404(job_id)
    if job.status != "done":
        raise HTTPException(409, f"job {job_id} is {job.status}, no result yet")
    return job.result


@router.get("/files/{job_id}/{fn}", response_class=PlainTextResponse)
def job_file(job_id: str, fn: str) -> PlainTextResponse:
    _job_or_404(job_id)
    if fn not in {"wt.pdb", "mut.pdb", "mut_aligned.pdb"}:
        raise HTTPException(404, "unknown artifact")
    path = get_job_manager().job_dir(job_id) / fn
    if not path.exists():
        raise HTTPException(404, f"artifact {fn} not written yet")
    return PlainTextResponse(path.read_text(), media_type="chemical/x-pdb")