#!/usr/bin/env python3
"""Stage 0 environment check: CUDA visibility, versions, omegafold import.

Writes data/report/env.json — the machine record referenced by the diploma report.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPORT = Path(__file__).resolve().parent.parent / "data" / "report"
REPORT.mkdir(parents=True, exist_ok=True)


def _cmd_output(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    env: dict = {"python": sys.version, "checked_at": datetime.now(timezone.utc).isoformat()}

    # GPU / driver facts straight from nvidia-smi
    env["nvidia_smi"] = _cmd_output(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,power.limit",
         "--format=csv,noheader"]
    )

    # nvcc version
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
            # real compute check: fp32 + fp16 matmul on GPU
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