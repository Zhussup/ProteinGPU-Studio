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
    # профиль инференса на запрос; None → оставить резидентный
    # 每次请求的推理配置；None → 沿用常驻配置
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
    # окно [start, end]: нумерация с 1, включительно
    # 窗口 [start, end]：从 1 开始、含端点
    local_window: tuple[int, int]
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
    # профили pLDDT по остаткам для графика (длина равна длине последовательности)
    # 逐残基 pLDDT 曲线，用于图表（与序列等长）
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
    mu: int = Field(default=1, ge=1, le=3)           # замен на вариант | 每个变体的替换数
    tau: float = Field(default=0.5, ge=0.0, le=1.0)  # температура Грантама | Grantham 谱温度
    k: int = Field(default=20, ge=2, le=40)          # размер ансамбля | 组合规模（exhaustive 忽略）
    seed: int | None = None  # None → детерминированный seed из конфига | None → 由配置派生确定性种子
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
            # exhaustive — всегда mu=1 по всем 19 заменам
            # exhaustive 模式：始终为 mu=1，遍历全部 19 种替换
            self.mu = 1
            self.k = 19
        return self


class EnsembleMutation(BaseModel):
    position: int
    wt_aa: str
    mut_aa: str


class EnsembleRow(BaseModel):
    label: str                          # "I44A" | "I44A+L3M"
    mutations: list[EnsembleMutation]   # якорь входит всегда | 始终包含锚定位点
    mut_aa: str | None = None           # только при одиночной замене | 仅单一替换时（ScanRow 对齐）
    local_rmsd: float
    global_rmsd: float
    tm_score: float
    plddt_mut: float
    dplddt: float        # plddt_mut − plddt_wt, среднее по структуре | 结构均值
    dplddt_local: float  # среднее ΔpLDDT по окну якоря — честная метрика | 锚定窗口平均 ΔpLDDT——诚实指标
    engine: str
    interpretation: Literal["stable", "moderate", "critical"]
    pdb_file: str        # "ens_XX.pdb", выровнен к WT | 已预对齐到 WT 构象


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
    # None → все; нумерация с 1, дубликаты убираются при запуске
    # None → 全部；从 1 开始，运行时去重
    positions: list[int] | None = None
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


class PlmScreenRequest(SequenceInput):
    """Whole-protein PLM screen (Meier 2021-style WT margin): all 19*L
    substitutions ranked from ONE OmegaPLM pass, then an optional bounded
    stage folding the most damaging substitutions per position.

    fold_top_k=0 keeps the run PLM-only (seconds); the folding budget is
    capped by max_folds so the job is bounded by construction.
    """
    # фолдинг в скрине: топ-K самых «повреждающих» замен на позицию
    # 折叠补充：每位置 K 个最“损伤”的替换
    fold_top_k: int = Field(default=1, ge=0, le=19)
    max_folds: int = Field(default=64, ge=0, le=400)


class PlmScreenResponse(BaseModel):
    job_id: str
    status: str
    length: int
    n_folds: int


class DmsValidationInput(SequenceInput):
    """Correlate the app's predictors with experimental DMS fitness.

    0-values = fast modes: sample_n=0 → no stratified folds; fold_positions_max=0
    → no per-position folds — PLM-only correlation (seconds).
    """
    assay_id: str = Field(min_length=3, max_length=80)
    # сколько стратифицированных по fitness вариантов дофолдить
    # сколько вариантов, стратифицированных по fitness, дополнительно свернуть
    sample_n: int = Field(default=48, ge=0, le=256)
    # на сколько позиций (по PLM-хрупкости) фолдить топ-1 замену
    # для скольких позиций (по PLM-уязвимости) свернуть топ-1 замену
    fold_positions_max: int = Field(default=40, ge=0, le=400)
    # seed стратифицированной выборки (None → 0, детерминизм)
    # seed стратифицированной выборки (None → 0, детерминизм)
    seed: int = Field(default=0, ge=0, le=2**31 - 1)


class DmsValidationResponse(BaseModel):
    job_id: str
    status: str
    length: int
    assay_id: str


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
    lengths: list[int] | None = None  # None → только заданная последовательность | None → 仅用给定序列
    repeats: int = Field(default=5, ge=1, le=20)


class BenchmarkResponse(BaseModel):
    job_id: str
    status: str
    rows: list[BenchmarkProfileRow] = []


class JobStatus(BaseModel):
    job_id: str
    kind: str  # predict | mutate | scan | ensemble | benchmark
    status: Literal["queued", "running", "done", "error", "cancelled"]
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