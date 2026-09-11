#!/usr/bin/env bash
# Stage 0: environment setup for ProteinGPU-Studio
# - creates .venv (Python 3.13 fallback logic inside)
# - installs torch cu124 wheel + all runtime deps
# - verifies CUDA + omegafold importability
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "[setup] creating venv"
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "[setup] upgrading pip"
pip install --upgrade pip wheel setuptools -q

echo "[setup] installing PyTorch (cu124)"
pip install torch --index-url https://download.pytorch.org/whl/cu124 -q

echo "[setup] installing runtime deps"
pip install -q omegafold biopython fastapi "uvicorn[standard]" pydantic-settings psutil scipy numpy pytest httpx

echo "[setup] verifying environment"
python scripts/check_env.py