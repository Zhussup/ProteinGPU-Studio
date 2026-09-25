"""OmegaFold wrapper with a RESIDENT model.

The OmegaFold CLI reloads ~700M weights from disk on every invocation; a web
service must load once and measure inference, not disk I/O. This module keeps
the model in memory for the process lifetime, exposes predict() with the same
inputs the CLI uses (pseudo-MSA generation, 10 recycling cycles), and returns
backbone coordinates + pLDDT + PDB text.

Weights: ~/.cache/omegafold_ckpt/model.pt or $OMEGAFOLD_WEIGHTS
         (download: https://helixon.s3.amazonaws.com/release1.pt)
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import numpy as np

from .base import PredictResult, validate_sequence

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = os.path.expanduser("~/.cache/omegafold_ckpt/model.pt")
WEIGHTS_URL = "https://helixon.s3.amazonaws.com/release1.pt"

# Те же параметры форварда, что и дефолты CLI OmegaFold.
# 前向参数与 OmegaFold CLI 默认值相同。
NUM_PSEUDO_MSA = 15
NUM_CYCLES = 10
MASK_RATE = 0.12


def weights_path() -> Path:
    return Path(os.environ.get("OMEGAFOLD_WEIGHTS", DEFAULT_WEIGHTS))


def ensure_weights() -> Path:
    """Return a local weights path, downloading if absent."""
    p = weights_path()
    if p.exists() and p.stat().st_size > 1e9:  # release1.pt ≈ 1.4 ГБ | release1.pt ≈ 1.4 GB
        return p
    if not p.parent.exists() and p.parent != Path("."):
        p.parent.mkdir(parents=True, exist_ok=True)
    import torch  # докачка через hub с поддержкой resume | 通过 hub 下载，支持断点续传
    logger.info("Downloading OmegaFold weights to %s ...", p)
    from torch import hub
    hub.download_url_to_file(WEIGHTS_URL, str(p))
    return p


class OmegaFoldModel:
    """Resident OmegaFold: load once, fold many."""

    def __init__(self, device: str | None = None, half: bool = False,
                 num_cycles: int = NUM_CYCLES):
        import torch
        import omegafold as of
        from omegafold import pipeline as of_pipeline

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.name = "omegafold-release1" + ("-fp16" if half else "")
        self._num_cycles = num_cycles

        wpath = ensure_weights()
        t0 = time.perf_counter()
        state = torch.load(str(wpath), map_location="cpu", weights_only=False)
        if "model" in state:
            state = state.pop("model")
        self._model = of.OmegaFold(of.make_config(1))
        self._model.load_state_dict(state)
        self._model.eval()
        self._model.to(device)
        # ВАЖНО: веса остаются fp32 даже при half=True — fp16-путь — это
        # autocast внутри predict() (обоснование в to_fp16 ниже). Наивный
        # .half() здесь роняет PLM attention ("Half but found Float").
        # 注意：即使 half=True 权重仍保持 fp32——fp16 路径是 predict() 内的
        # autocast（理由见下方 to_fp16）。直接 .half() 会让 PLM 注意力崩溃
        # （"Half but found Float"）。
        self._half = half
        logger.info("OmegaFold loaded to %s in %.1fs", device, time.perf_counter() - t0)

        # Forward cfg: флаги точности эквивалентны CLI allow_tf32=True.
        # CLI всегда передаёт Namespace fwd_cfg; GAU в OmegaPLM безусловно
        # разыменовывает fwd_cfg.subbatch_size — None упал бы.
        # 前向配置：精度标志等价于 CLI 的 allow_tf32=True。
        # CLI 总是传入 fwd_cfg Namespace；OmegaPLM 的 GAU 无条件解引用
        # fwd_cfg.subbatch_size，传 None 会崩溃。
        import argparse
        self._fwd_cfg = argparse.Namespace(
            subbatch_size=None, num_recycle=num_cycles)
        if device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

    # -- внутренности -------------------------------------------------------
    # -- 内部实现 ------------------------------------------------------------
    def _make_inputs(self, seq: str):
        """Pseudo-MSA inputs, identical in spirit to pipeline.fasta2inputs."""
        import torch
        from omegafold.utils.protein_utils import residue_constants as rc

        aatype = torch.LongTensor(
            [rc.restypes_with_x.index(aa) for aa in seq]
        ).to(self.device)
        mask = torch.ones_like(aatype).float()
        num_res = len(aatype)
        data = []
        g = torch.Generator(device="cpu")
        g.manual_seed(num_res)  # детерминированно по длине, как в CLI | 按长度确定性，与 CLI 一致
        for _ in range(self._num_cycles):
            p_msa = aatype[None, :].repeat(NUM_PSEUDO_MSA, 1).cpu()
            p_msa_mask = torch.rand([NUM_PSEUDO_MSA, num_res], generator=g).gt(MASK_RATE)
            p_msa_mask = torch.cat((mask[None, :].cpu(), p_msa_mask), dim=0)
            p_msa = torch.cat((aatype[None, :].cpu(), p_msa), dim=0)
            p_msa[~p_msa_mask.bool()] = 21
            data.append({"p_msa": p_msa, "p_msa_mask": p_msa_mask})
        # аналог recursive_to: переносим всю структуру на устройство
        # 等价于 recursive_to：把整个结构移到设备
        return [{k: v.to(self.device) for k, v in d.items()} for d in data]

    # -- публичный API -------------------------------------------------------
    # -- 公共 API -------------------------------------------------------------
    def predict(self, seq: str) -> PredictResult:
        import torch
        from omegafold import pipeline as of_pipeline

        seq = validate_sequence(seq)
        inputs = self._make_inputs(seq)
        with torch.no_grad(), torch.autocast(
                "cuda", dtype=torch.float16,
                enabled=self._half and self.device == "cuda"):
            out = self._model(inputs, predict_with_confidence=True,
                              fwd_cfg=self._fwd_cfg)

        pos14 = out["final_atom_positions"].detach().float().cpu()   # [N, 14, 3]
        conf = out["confidence"].detach().float().cpu()              # [N] in [0,1]
        aatype = inputs[0]["p_msa"][0]                                # [N]

        # Основной остов N, CA, C, O = слоты 0, 1, 2, 3 в atom14
        # 主链 N, CA, C, O = atom14 的槽位 0, 1, 2, 3
        bb = pos14[:, :4, :].numpy()
        plddt = (conf * 100.0).numpy()

        # save_pdb пишет в файл; рендерим во временный файл и читаем обратно.
        # save_pdb 只能写文件；先写到临时文件再读回。
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as f:
            tmp = f.name
        of_pipeline.save_pdb(
            pos14=pos14, b_factors=conf * 100, sequence=aatype,
            mask=inputs[0]["p_msa_mask"][0], save_path=tmp, model=0)
        pdb_text = Path(tmp).read_text()
        os.unlink(tmp)

        return PredictResult(
            coords_backbone=bb,
            plddt=plddt,
            pdb_text=pdb_text,
            seq=seq,
            plddt_mean=float(conf.mean() * 100.0),
        )

    def to_fp16(self) -> None:
        """Profile switch: fp16 compute via autocast (CUDA only).

        OmegaFold release1 is not half()-safe: its PLM attention mixes fp32
        buffers (relpos bias, scaling) with weights, so naive .half() crashes
        with "expected scalar type Half but found Float". Weights stay fp32;
        autocast runs tensor-core matmuls in fp16 and keeps reductions fp32 —
        the standard mixed-precision recipe.
        """
        if self.device == "cuda" and not self._half:
            self._half = True
            self.name = "omegafold-release1-fp16-autocast"

    def to_fp32(self) -> None:
        import torch
        if self.device == "cuda" and self._half:
            self._model.float()
            self._half = False
            self.name = "omegafold-release1"

    def clear_gpu(self) -> None:
        import torch, gc
        del self._model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def close(self) -> None:
        try:
            self.clear_gpu()
        except Exception:
            pass