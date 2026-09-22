#!/usr/bin/env bash
# Stage 0: environment setup for ProteinGPU-Studio
# - creates .venv (Python 3.13 fallback logic inside)
# - installs torch cu124 wheel + all runtime deps
# - pins omegafold to an upstream snapshot (NOT on PyPI — manual copy)
# - verifies CUDA + omegafold importability + package provenance
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
pip install -q biopython fastapi "uvicorn[standard]" pydantic-settings psutil scipy numpy pytest httpx

# omegafold is not published on PyPI (the name 404s there), and its own
# setup.py refuses Python >= 3.11 while pinning torch 1.12+cu113. The code is
# Apache-2.0, so we vendor a pristine upstream snapshot instead: download the
# repo tarball at a pinned commit, copy the package + its LICENSE into
# site-packages. check_env.py then verifies the tree against a sha256
# manifest — internal APIs are not a contract, so any silent drift must fail
# loudly rather than quietly skew predictions.
OMEGAFOLD_SHA=313c873ad190b64506a497c926649e15fcd88fcd
SITE="$(python -c 'import site; print(site.getsitepackages()[0])')"
if [ ! -d "$SITE/omegafold" ]; then
  echo "[setup] vendoring omegafold @ $OMEGAFOLD_SHA (Apache-2.0, manual copy)"
  TMP="$(mktemp -d)"
  curl -fsSL "https://github.com/HeliXonProtein/OmegaFold/archive/$OMEGAFOLD_SHA.tar.gz" -o "$TMP/src.tar.gz"
  tar -xzf "$TMP/src.tar.gz" -C "$TMP"
  SRC="$TMP/OmegaFold-$OMEGAFOLD_SHA"
  cp -r "$SRC/omegafold" "$SITE/omegafold"
  # keep the copyright notice with the copy (Apache-2.0 §4a)
  cp "$SRC/LICENSE" "$SITE/omegafold/LICENSE"
  rm -rf "$TMP"
else
  echo "[setup] omegafold already vendored"
fi

echo "[setup] verifying environment"
python scripts/check_env.py