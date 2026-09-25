"""Backend configuration (env-overridable)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

REPO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Артефакты заданий лежат здесь (в .gitignore): data/jobs/<job_id>/*.pdb + result.json
    # 任务产物存放于此（已 gitignore）：data/jobs/<job_id>/*.pdb + result.json
    data_dir: Path = REPO / "data"
    db_path: Path = REPO / "data" / "jobs.sqlite3"

    # профиль фолдинга: auto (настоящий, если веса+CUDA, иначе dummy) | omegafold | dummy
    # 折叠配置：auto（有权重+CUDA 时用真实模型，否则 dummy）| omegafold | dummy
    folding_profile: str = "auto"

    # пределы длины последовательности (план: 10..600; в демо ниже — для откатного CPU-режима)
    # 序列长度限制（计划：10..600；演示中更低，用于 CPU 回退）
    seq_min: int = 10
    seq_max: int = 600

    # окно локального RMSD: ±radius остатков вокруг мутации
    # 局部 RMSD 窗口：突变位点周围 ±radius 个残基
    local_radius: int = 10

    # пороговая трактовка локального RMSD (Å)
    # 局部 RMSD 的阈值判读（Å）
    rmsd_stable_below: float = 1.0
    rmsd_critical_above: float = 2.0

    # кэш WT: sha1(seq) → путь к PDB
    # WT 缓存：sha1(seq) → PDB 路径
    wt_cache_size: int = 128

    host: str = "127.0.0.1"
    port: int = 8000

    class Config:
        env_prefix = "PGS_"
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    (s.data_dir / "jobs").mkdir(exist_ok=True)
    return s