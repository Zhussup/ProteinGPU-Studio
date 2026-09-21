# ProteinGPU-Studio

**English** | [Русский](README_RU.md) | [中文](README_ZH.md)

<div align="center">

**In-silico mutagenesis backed by real structure prediction — with an honest CPU vs GPU benchmark.**

Type a protein, mutate one residue, watch WT and mutant fold — then see exactly
what it cost on CPU vs GPU, measured honestly.

![Demo: KRAS G12D — 3D overlay, metrics, pLDDT chart](docs/assets/demo.gif)

![Python](https://img.shields.io/badge/python-3.13-black?style=flat-square&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.6-black?style=flat-square&logo=pytorch&logoColor=white)
![CUDA](https://img.shields.io/badge/CUDA-12.4-black?style=flat-square&logo=nvidia&logoColor=white)
![React](https://img.shields.io/badge/React%20%2B%20Vite-black?style=flat-square&logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-black?style=flat-square&logo=fastapi&logoColor=white)

</div>

## What is this

A web platform that mutates a protein sequence, re-folds WT and mutant with a real
structure-prediction model (OmegaFold; ESMFold fallback), overlays the two structures
and reports how much the mutation actually changed the fold — global/local RMSD via
Kabsch alignment, TM-score, pLDDT per chain. The inference stack (CPU / fp32-GPU /
fp16-GPU) is benchmarked with median + IQR on a 60 W laptop GPU, and the alignment
kernel exists in three implementations (NumPy, C++17 OpenMP, CUDA) so you can see
where the time really goes.

Everything on screen is real: no fake progress bars, no dummy models — the UI shows
the actual backend pipeline stages, and the demo above is a full live run.

## Features

- **Real folding models** — OmegaFold primary, ESMFold fallback; CPU / fp32-GPU / fp16-GPU profiles switchable in the UI
- **WT vs MUT analysis** — Kabsch-aligned RMSD (global + local window), TM-score, pLDDT WT/mut/Δ, alignment verdict
- **C++17 / CUDA HPC core** — batched Kabsch + RMSD kernel behind PyBind11, with PCIe-copy vs device-resident paths measured separately
- **Saturation scan** — all 19 substitutions at one position, ranked table + chart
- **Per-residue pLDDT chart** — WT vs mutant, hoverable
- **Research presets** — KRAS G12D, p53 R82H, HbB E6V, lysozyme I56T, Trp-cage W6F, Aβ42 E22G, α-syn A53T, GFP S65T
- **DNA FASTA input** — upload a gene, get the codon→amino-acid translation window
- **Honest job pipeline** — per-stage progress from the real backend (including "waiting for GPU slot"), job history in SQLite

## Benchmarks

Measured on the machine this project was built on: **RTX 3050 Laptop 6 GB at a 60 W
power limit**, torch 2.6.0+cu124. All numbers are **median + IQR** over repeats with
2 warmup runs dropped — a 60 W laptop throttles, and a single measurement lies.

OmegaFold inference, 76-residue sequence (KRAS):

| Profile | Wall time (median) | VRAM peak |
|---|---|---|
| CPU | 143.5 s | — |
| fp32-GPU | 11.6 s | 3.27 GB |
| fp16-GPU | **8.7 s** (16× vs CPU) | 4.86 GB |

Note the trade-off the table makes visible: fp16 is faster but *heavier* in VRAM.

Kabsch RMSD kernel, 1024 structure pairs × 256 atoms:

| Engine | Wall time (median) |
|---|---|
| NumPy | 31.8 ms |
| C++17 OpenMP | **0.36 ms** (88× vs NumPy) |
| CUDA (PCIe copies) | 3.2 ms |
| CUDA (device-resident) | 1.8 ms |

The CUDA kernel only wins once the data lives on the device — crossing PCIe costs
more than the kernel itself. Reproduce: `python scripts/10_bench_inference.py`,
`python scripts/11_bench_kernels.py`.

## Quickstart

```bash
./scripts/00_setup_env.sh             # venv + dependencies
source .venv/bin/activate
make -C hpc_core cpu                  # C++ core (CUDA optional: make cuda)

uvicorn backend.app.main:app --port 8077
cd frontend && npm install && npm run dev
```

Open the frontend, pick a preset or paste a FASTA, run WT + mutant.
Full pipeline check: `python scripts/e2e_smoke.py` (ubiquitin + I44A/I3L/P19G).

## Architecture

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

- `backend/` — FastAPI: job queue (SQLite), validation, telemetry
- `ml/` — folding-model wrappers + CPU/GPU-fp32/fp16 profiles
- `hpc_core/` — C++17 + CUDA kernel: Kabsch, RMSD, PyBind11 bindings
- `frontend/` — Vite + React + TypeScript, 3Dmol.js + Plotly.js
- `scripts/` — environment setup, spike tests, benchmarks, demo recorder

The demo GIF is recorded by a Playwright script that drives the real UI end-to-end
on a real GPU run (`scripts/20_demo_video.py`) — including a check that the recorded
job ran the real model, not a stub.

## Credits

- [OmegaFold](https://github.com/HeliXonProtein/OmegaFold) and [ESMFold](https://github.com/facebookresearch/esm) — structure prediction
- [3Dmol.js](https://3dmol.csb.pitt.edu/) — molecular viewer · [Plotly.js](https://plotly.com/javascript/) — charts
- [PyBind11](https://github.com/pybind/pybind11) — C++/Python bindings