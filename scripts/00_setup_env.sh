#!/usr/bin/env bash
# Этап 0: подготовка окружения для ProteinGPU-Studio
# - создаёт .venv (логика отката на Python 3.13 внутри)
# - ставит wheel torch cu124 + все runtime-зависимости
# - закрепляет omegafold на upstream-снимке (НЕ на PyPI — ручное копирование)
# - проверяет CUDA + импортируемость omegafold + происхождение пакетов
# 阶段 0：ProteinGPU-Studio 的环境准备
# - 创建 .venv（内部含 Python 3.13 回退逻辑）
# - 安装 torch cu124 wheel + 全部运行时依赖
# - 将 omegafold 固定到上游快照（PyPI 上没有——手动复制）
# - 校验 CUDA、omegafold 可导入性以及包来源
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

# omegafold не опубликован на PyPI (имя там 404), а его собственный
# setup.py отказывается от Python >= 3.11 и при этом приколачивает
# torch 1.12+cu113. Код под Apache-2.0, поэтому мы кладём себе чистый
# upstream-снимок: скачиваем tarball репозитория на закреплённом коммите
# и копируем пакет + его LICENSE в site-packages. Затем check_env.py
# сверяет дерево с sha256-манифестом — внутренние API не контракт, поэтому
# любой тихий дрейф должен падать громко, а не незаметно искажать предсказания.
# omegafold 未发布到 PyPI（该名称在彼处返回 404），其自身的 setup.py
# 拒绝 Python >= 3.11 且同时钉死 torch 1.12+cu113。代码为 Apache-2.0，
# 因此我们改为自己引入一份干净的上游快照：在固定 commit 下载仓库
# tarball，把包及其 LICENSE 复制进 site-packages。随后 check_env.py
# 按 sha256 清单校验代码树——内部 API 不是契约，任何无声漂移都必须
# 大声失败，而不是悄悄扭曲预测结果。
OMEGAFOLD_SHA=313c873ad190b64506a497c926649e15fcd88fcd
SITE="$(python -c 'import site; print(site.getsitepackages()[0])')"
if [ ! -d "$SITE/omegafold" ]; then
  echo "[setup] vendoring omegafold @ $OMEGAFOLD_SHA (Apache-2.0, manual copy)"
  TMP="$(mktemp -d)"
  curl -fsSL "https://github.com/HeliXonProtein/OmegaFold/archive/$OMEGAFOLD_SHA.tar.gz" -o "$TMP/src.tar.gz"
  tar -xzf "$TMP/src.tar.gz" -C "$TMP"
  SRC="$TMP/OmegaFold-$OMEGAFOLD_SHA"
  cp -r "$SRC/omegafold" "$SITE/omegafold"
  # сохраняем уведомление об авторских правах вместе с копией (Apache-2.0 §4a)
  # 复制时保留版权声明（Apache-2.0 §4a）
  cp "$SRC/LICENSE" "$SITE/omegafold/LICENSE"
  rm -rf "$TMP"
else
  echo "[setup] omegafold already vendored"
fi

echo "[setup] verifying environment"
python scripts/check_env.py