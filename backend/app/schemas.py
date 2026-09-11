"""Pydantic v2 request/response schemas.

Sequence alphabet/length enforced here; mutation consistency (sequence[pos-1]
== wt_aa) checked with a model_validator so bad requests never reach the GPU.
Every RMSD-bearing response carries the `engine` tag ("cuda" | "cpp" | "numpy")
— the honesty rule of the project: no number without its engine.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AA_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")


class SequenceInput(BaseModel):
    sequence: str = Field(min_length=10, max_length=600)

    @field_validator("sequence")
    @classmethod
    def _check(cls, v: str) -> str:
        s = "".join(v.split()).upper()
        if not AA_RE.fullmatch(s):
            raise ValueError("sequence must contain only standard amino acids")
        return s


class PredictRequest(SequenceInput):
    pass


class MutateRequest(SequenceInput):
    position: int = Field(ge=1)
    mutant_aa: str = Field(pattern=r"^[ACDEFGHIKLMNPQRSTVWY]$")

    @model_validator(mode="after")
    def _pos_in_range(self):
        if self.position > len(self.sequence):
            raise ValueError(
                f"position {self.position} out of range 1..{len(self.sequence)}")
        return self


class PredictResponse(BaseModel):
    job_id: str
    status: str
    length: int
    plddt_mean: float | None = None
    model: str | None = None


class RmsdResult(BaseModel):
    global_rmsd: float
    local_rmsd: float
    local_window: tuple[int, int]  # 1-based inclusive [start, end]
    tm_score: float
    plddt_wt: float
    plddt_mut: float
    interpretation: Literal["stable", "moderate", "critical"]
    engine: str


class MutationResult(BaseModel):
    job_id: str
    status: str
    wt_sequence: str
    mutant_sequence: str
    position: int
    wt_aa: str
    mutant_aa: str
    model: str | None = None
    rmsd: RmsdResult | None = None


class BenchmarkProfileRow(BaseModel):
    profile: str
    length: int
    wall_median_s: float
    wall_iqr_s: float
    vram_peak_mb: float | None = None
    repeats: int


class BenchmarkRequest(BaseModel):
    sequence: str = Field(min_length=10, max_length=300)
    profiles: list[str] = Field(default_factory=lambda: ["fp32-gpu"])
    lengths: list[int] | None = None  # None → use the given sequence only
    repeats: int = Field(default=5, ge=1, le=20)


class BenchmarkResponse(BaseModel):
    job_id: str
    status: str
    rows: list[BenchmarkProfileRow] = []


class JobStatus(BaseModel):
    job_id: str
    kind: str  # predict | mutate | benchmark
    status: Literal["queued", "running", "done", "error"]
    progress: float = 0.0
    message: str | None = None
    created_at: str
    finished_at: str | None = None
    error: str | None = None


def interpret_rmsd(local_rmsd: float, stable_below: float = 1.0,
                   critical_above: float = 2.0) -> str:
    """Interpretation bands from the ТЗ: <1 Å stable, 1–2 moderate, >=2 critical."""
    if local_rmsd < stable_below:
        return "stable"
    if local_rmsd < critical_above:
        return "moderate"
    return "critical"