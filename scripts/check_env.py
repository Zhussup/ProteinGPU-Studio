#!/usr/bin/env python3
"""Stage 0 environment check: CUDA visibility, versions, omegafold import.

Writes data/report/env.json — the machine record referenced by the diploma report.
"""
import hashlib
import json
import shutil
import site
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path(__file__).resolve().parent.parent / "data" / "report"
REPORT.mkdir(parents=True, exist_ok=True)

# Закреплённый снапшот omegafold из upstream (Helixon/OmegaFold, Apache-2.0).
# Пакета нет на PyPI, поэтому scripts/00_setup_env.sh вендорит дерево на этом
# коммите, а check_env сверяет каждый файл с sha256-манифестом: внутренние API
# не контракт, поэтому незамеченный дрейф (неполная копия, случайная правка)
# должен падать громко, а не тихо перекашивать предсказания.
# 锁定的 omegafold 上游快照（Helixon/OmegaFold，Apache-2.0）。
# 该包不在 PyPI 上，因此 scripts/00_setup_env.sh 以此提交 vendored 整棵树，
# check_env 用 sha256 清单校验每个文件：内部 API 不是契约，任何未被察觉的
# 漂移（复制不全、误编辑）都必须响亮失败，而不是悄悄扭曲预测。
OMEGAFOLD_SHA = "313c873ad190b64506a497c926649e15fcd88fcd"
OMEGAFOLD_TREE_SHA256 = "a04905e7b08afee6c922f40e76fa6eace73fa187b6571cb9744c851da716e67b"


def omegafold_tree_digest(pkg_dir: Path) -> str | None:
    """Content manifest of the vendored tree: sha256 over sorted (path, file-hash).

    __pycache__/ artifacts are excluded — they appear and disappear at
    runtime and say nothing about the source.
    """
    if not pkg_dir.is_dir():
        return None
    h = hashlib.sha256()
    for f in sorted(p for p in pkg_dir.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts):
        h.update(f.relative_to(pkg_dir).as_posix().encode())
        h.update(b"\0")
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def _cmd_output(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    env: dict = {"python": sys.version, "checked_at": datetime.now(timezone.utc).isoformat()}

    # факты о GPU/драйвере прямо из nvidia-smi
    # 直接从 nvidia-smi 获取 GPU/驱动信息
    env["nvidia_smi"] = _cmd_output(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,power.limit",
         "--format=csv,noheader"]
    )

    # версия nvcc
    # nvcc 版本
    try:
        out = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=10).stdout
        env["nvcc"] = out.strip().splitlines()[-1] if out.strip() else None
    except OSError:
        env["nvcc"] = None

    ok = True
    try:
        import torch  # noqa: PLC0415

        env["torch_version"] = torch.__version__
        env["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            env["gpu_name"] = torch.cuda.get_device_name(0)
            env["gpu_capability"] = ".".join(map(str, torch.cuda.get_device_capability(0)))
            env["vram_total_mb"] = round(total / 1024**2)
            env["vram_free_mb"] = round(free / 1024**2)
            # реальная проверка вычислений: fp32 + fp16 matmul на GPU
            # 真实计算检查：GPU 上的 fp32 + fp16 矩阵乘
            x = torch.randn(1024, 1024, device="cuda")
            _ = (x @ x).sum().item()
            _ = (x.half() @ x.half()).float().sum().item()
            env["gpu_matmul_ok"] = True
        else:
            ok = False
            env["gpu_matmul_ok"] = False
    except Exception as e:  # noqa: BLE001 — report must capture any failure
        ok = False
        env["torch_error"] = repr(e)

    try:
        import omegafold  # noqa: F401, PLC0415

        env["omegafold_import"] = True
    except Exception as e:  # noqa: BLE001
        ok = False
        env["omegafold_import"] = False
        env["omegafold_error"] = repr(e)

    # пин провенанса: вендоренное дерево должно побайтно совпадать со снапшотом
    # 来源锁定：vendored 树必须与锁定快照逐字节一致
    digest = omegafold_tree_digest(Path(site.getsitepackages()[0]) / "omegafold")
    env["omegafold_sha"] = OMEGAFOLD_SHA
    env["omegafold_tree_sha256"] = digest
    env["omegafold_tree_ok"] = digest == OMEGAFOLD_TREE_SHA256
    if not env["omegafold_tree_ok"]:
        ok = False

    try:
        import Bio  # noqa: PLC0415

        env["biopython"] = Bio.__version__
    except Exception:  # noqa: BLE001
        ok = False
        env["biopython"] = None

    env["status"] = "ok" if ok else "fail"
    out = REPORT / "env.json"
    out.write_text(json.dumps(env, indent=2, ensure_ascii=False))
    print(json.dumps(env, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())