# ProteinGPU-Studio: In Silico Mutagenesis & Inference Benchmark

Веб-платформа для предиктивного 3D-моделирования белковых структур, анализа точечных мутаций
(WT vs MUT, Kabsch + RMSD на C++/CUDA) и сравнительного бенчмаркинга инференса CPU vs GPU.

## Архитектура

```
[Web Client: React / 3Dmol.js / Plotly]
                 │ REST (polling)
                 ▼
[Backend Gateway: FastAPI]
        │                    │
        ▼                    ▼
[ML Inference Engine]   [C++/CUDA HPC Core]
(OmegaFold / PyTorch)   (Kabsch / RMSD, PyBind11)
```

- `backend/` — FastAPI: очередь задач (SQLite), валидация, телеметрия
- `ml/` — обёртки folding-моделей (OmegaFold primary, ESMFold fallback), профили CPU/GPU-fp32/fp16
- `hpc_core/` — C++17 + CUDA ядро: алгоритм Кабша, RMSD, PyBind11-биндинг
- `frontend/` — Vite + React + TypeScript, тёмная тема, 3Dmol.js + Plotly.js
- `scripts/` — установка окружения, spike-тесты, бенчмарки

## Быстрый старт

```bash
./scripts/00_setup_env.sh          # venv + зависимости
source .venv/bin/activate
python scripts/01_spike_folding_fit.py   # выбор ML-модели (decision gate)
make -C hpc_core cpu               # C++ ядро (без CUDA)
```

Backend: `uvicorn backend.app.main:app --reload` · Frontend: `cd frontend && npm run dev`