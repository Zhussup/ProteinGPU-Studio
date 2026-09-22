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

Profile = Literal["auto", "fp32-gpu", "fp16-gpu", "cpu", "dummy"]


class SequenceInput(BaseModel):
    sequence: str = Field(min_length=10, max_length=600)
    # per-request inference profile; None → keep the resident one
    profile: Profile | None = None

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
    # per-residue pLDDT profiles for the chart (same length as the sequence)
    plddt_wt_list: list[float] | None = None
    plddt_mut_list: list[float] | None = None


class ScanRequest(BaseModel):
    """Saturation-mutagenesis scan: all 19 substitutions at one position."""
    sequence: str = Field(min_length=10, max_length=600)
    position: int = Field(ge=1)
    profile: Profile | None = None

    @field_validator("sequence")
    @classmethod
    def _check(cls, v: str) -> str:
        s = "".join(v.split()).upper()
        if not AA_RE.fullmatch(s):
            raise ValueError("sequence must contain only standard amino acids")
        return s

    @model_validator(mode="after")
    def _pos_in_range(self):
        if self.position > len(self.sequence):
            raise ValueError(
                f"position {self.position} out of range 1..{len(self.sequence)}")
        return self


class ScanRow(BaseModel):
    mut_aa: str
    local_rmsd: float
    global_rmsd: float
    tm_score: float
    plddt_mut: float
    dplddt: float
    engine: str
    interpretation: Literal["stable", "moderate", "critical"]


class ScanResponse(BaseModel):
    job_id: str
    status: str
    length: int


class EnsembleRequest(BaseModel):
    """Mutagenesis-strength ensemble (dum.md): K variants sampled by (mu, tau)
    at one anchor position — the position's sensitivity is the DISTRIBUTION of
    structural responses across the variants. mode="exhaustive" folds all 19
    single substitutions (mu=1) — the /scan workload, kept for the lossless
    migration: its rows/ranking/artifacts are a superset of the scan's."""
    sequence: str = Field(min_length=10, max_length=600)
    position: int = Field(ge=1)
    mode: Literal["sampled", "exhaustive"] = "sampled"
    mu: int = Field(default=1, ge=1, le=3)           # substitutions per variant
    tau: float = Field(default=0.5, ge=0.0, le=1.0)  # Grantham spectrum temperature
    k: int = Field(default=20, ge=2, le=40)          # ensemble size (exhaustive ignores)
    seed: int | None = None  # None → deterministic derived seed from the config
    profile: Profile | None = None

    @field_validator("sequence")
    @classmethod
    def _check(cls, v: str) -> str:
        s = "".join(v.split()).upper()
        if not AA_RE.fullmatch(s):
            raise ValueError("sequence must contain only standard amino acids")
        return s

    @model_validator(mode="after")
    def _normalize(self):
        if self.position > len(self.sequence):
            raise ValueError(
                f"position {self.position} out of range 1..{len(self.sequence)}")
        if self.mode == "exhaustive":
            # exhaustive is mu=1 over all 19 substitutions, always
            self.mu = 1
            self.k = 19
        return self


class EnsembleMutation(BaseModel):
    position: int
    wt_aa: str
    mut_aa: str


class EnsembleRow(BaseModel):
    label: str                          # "I44A" | "I44A+L3M"
    mutations: list[EnsembleMutation]   # the anchor is always included
    mut_aa: str | None = None           # iff a single substitution (ScanRow parity)
    local_rmsd: float
    global_rmsd: float
    tm_score: float
    plddt_mut: float
    dplddt: float        # plddt_mut - plddt_wt, structure means (ScanRow parity)
    dplddt_local: float  # mean ΔpLDDT over the anchor window — the honest metric
    engine: str
    interpretation: Literal["stable", "moderate", "critical"]
    pdb_file: str        # "ens_XX.pdb", pre-aligned to the WT frame


class StatsBlock(BaseModel):
    mean: float
    std: float
    median: float
    iqr: float
    min: float
    max: float


class EnsembleHeadline(BaseModel):
    level: Literal["quiet", "moderate", "strong"]
    width: Literal["narrow", "moderate", "wide"]
    iqr_ratio: float
    median_local_rmsd: float
    median_abs_dplddt_local: float


class EnsembleResponse(BaseModel):
    job_id: str
    status: str
    length: int
    wt_aa: str
    mode: str
    mu: int
    tau: float
    k: int


class ScanMapRequest(BaseModel):
    """Sensitivity map (dum.md §5): the 19-vector at EVERY position.

    This is the expensive honest job: 19*L folds (WT once from cache). A
    position subset keeps the demo bounded — the full map is the same loop.
    positions=None means "all".
    """
    sequence: str = Field(min_length=10, max_length=600)
    positions: list[int] | None = None  # None → all; 1-based, deduped on run
    profile: Profile | None = None

    @field_validator("sequence")
    @classmethod
    def _check(cls, v: str) -> str:
        s = "".join(v.split()).upper()
        if not AA_RE.fullmatch(s):
            raise ValueError("sequence must contain only standard amino acids")
        return s

    @model_validator(mode="after")
    def _positions_in_range(self):
        if self.positions:
            if len(set(self.positions)) != len(self.positions):
                raise ValueError("duplicate positions")
            bad = [p for p in self.positions if not (1 <= p <= len(self.sequence))]
            if bad:
                raise ValueError(
                    f"positions out of range 1..{len(self.sequence)}: {bad}")
        return self


class ScanMapResponse(BaseModel):
    job_id: str
    status: str
    length: int
    n_positions: int
    n_folds: int


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
    kind: str  # predict | mutate | scan | ensemble | benchmark
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