"""ProteinGPU-Studio backend entry point.

Run: .venv/bin/uvicorn backend.app.main:app --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

REPO = Path(__file__).resolve().parents[2]
for p in (str(REPO / "ml"), str(REPO / "hpc_core" / "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from .routers import benchmark, jobs, predict, system, translate  # noqa: E402

app = FastAPI(
    title="ProteinGPU-Studio",
    description="WT/mutant protein folding + Kabsch RMSD (C++/CUDA) + CPU/GPU benchmarks",
    version="0.1.0",
)

# Удобство для разработки: Vite dev-сервер на :5173 обращается к этому API.
# 开发便利：:5173 上的 Vite 开发服务器访问本 API。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(translate.router)
app.include_router(predict.router)
app.include_router(benchmark.router)
app.include_router(jobs.router)


@app.on_event("shutdown")
def _shutdown() -> None:
    from .services.folding_service import get_folding_service
    get_folding_service().close()