"""Backend configuration (env-overridable)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

REPO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Job artifacts live here (gitignored): data/jobs/<job_id>/*.pdb + result.json
    data_dir: Path = REPO / "data"
    db_path: Path = REPO / "data" / "jobs.sqlite3"

    # folding profile: auto (real if weights+CUDA else dummy) | omegafold | dummy
    folding_profile: str = "auto"

    # sequence limits (plan: 10..600; demo caps lower for CPU fallback)
    seq_min: int = 10
    seq_max: int = 600

    # local RMSD window ±radius residues around the mutation
    local_radius: int = 10

    # stable-threshold interpretation of local RMSD (Å)
    rmsd_stable_below: float = 1.0
    rmsd_critical_above: float = 2.0

    # WT cache: sha1(seq) → PDB path
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