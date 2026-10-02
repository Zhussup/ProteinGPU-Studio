"""Zero-shot substitution scoring from the OmegaPLM, weight-tied.

The vendored OmegaFold has NO language-model head (verified against
release1.pt and the omegafold package: no vocab projection exists — the
only heads are pLDDT/torsion/distogram). The only vocab-capable pair in
the whole model is the post-`output_norm` node state [*, L, 1280] and
`omega_plm.input_embedding.weight` [23, 1280]: logits exist only through
weight-tying, `logits = node @ W.T`.

Protocol ("wild-type margin", Meier et al. 2021 / ESM-1v style): ONE
forward pass of the PLM on the fully unmasked WT sequence. tokens [1, L]
is consistent with the vendored call: pseudo-MSA rows are independent
batch elements in the GAU stack, so a single unmasked row carries exactly
that sequence's context. log-softmax over the 20 canonical columns
(X = 20, padding = 21 excluded) — margins are log-probability
differences and depend on nothing outside this one pass:
    margin(i, wt->b) = lp[i, b] - lp[i, wt]
No folding, no MSA, no sampling — the cheap zero-shot baseline the
structural response is compared against (dum.md §3 two-tier screen).

Run in fp32 WITHOUT autocast even on the fp16 profile: the autocast lives
only inside OmegaFoldModel.predict; feeding a log-softmax fp16 logits is
the classic NaN trap. The scorer is deterministic; the dummy
implementation exists for tests and UI wiring and must never appear in
report numbers (same rule as DummyModel).

Вендорное дерево не правим: scorer лишь вызывает omega_plm снаружи.
Вендорное дерево не изменяемуем: score只从外部调用 omega_plm。
"""
from __future__ import annotations

import argparse
import hashlib
import time
from dataclasses import dataclass

import numpy as np

from .base import AA_RE, validate_sequence

# Венторный словарь (omegafold.utils.protein_utils.residue_constants.restypes):
# порядок ОТЛИЧАЕТСЯ от алфавита приложения (AA_RE) — соответствие столбцов
# логитов с буквами критично, поэтому сквозной guard в OmegaPlmScorer.
# Vendored alphabet differs from the app alphabet; a drift guard in
# OmegaPlmScorer turns any upstream reordering into a loud failure.
# 供应商词典与应用字母表不同；词汇顺序漂移由守卫响亮处理。
OF_RESTYPES = "ARNDCQEGHILKMFPSTWYV"   # A=0, R=1, N=2, D=3, C=4, Q=5, E=6, G=7, H=8,
                                       # I=9, L=10, K=11, M=12, F=13, P=14, S=15, T=16,
                                       # W=17, Y=18, V=19; X=OF_X, padding=21
OF_X = 20
OF_RESIDX = {aa: i for i, aa in enumerate(OF_RESTYPES)}

# Колонки результата — алфавит приложения (тот же порядок, что в
# sensibility-модулях: grantham, SECTOR_OF, CSV).
# 结果列使用应用字母表（与 grantham/SECTOR_OF/CSV 一致）。
STD_AA = AA_RE


@dataclass
class PlmScoreResult:
    """One forward pass: log-probs and margins for every (pos, substitution).

    Columns of both matrices are STD_AA order; margins[i, j] is the log
    margin of substituting the WT residue at position i with STD_AA[j]
    (so margins[i, wt_col] == 0.0 by construction).
    """
    seq: str
    logprobs: np.ndarray   # [L, 20] log p(token | sequence, pos)
    margins: np.ndarray    # [L, 20]
    scorer: str            # "omegaplm-tied" | "dummy-plm"
    device: str
    elapsed_s: float

    def margin(self, pos0: int, alt_aa: str) -> float:
        """Log margin of one substitution; pos0 is 0-based."""
        return float(self.margins[pos0, STD_AA.index(alt_aa)])

    def logprob(self, pos0: int, aa: str) -> float:
        return float(self.logprobs[pos0, STD_AA.index(aa)])


def make_tokens(seq: str, device: str):
    """Tokens + mask exactly in the vendored call convention.

    Mirrors omegafold_model._make_inputs: LongTensor of residue indices
    (rc.restypes_with_x order, X=20 unused here — the schema rejects X),
    float ones mask of the same shape. PLM forward takes tokens/mask of
    shape [*, L]; ONE row (unlike the 16-row pseudo-MSA of a full fold).
    """
    import torch
    tokens = torch.LongTensor([[OF_RESIDX[aa] for aa in seq]]).to(device)
    mask = torch.ones_like(tokens).float()
    return tokens, mask


def has_plm(model) -> bool:
    """True if the resident model carries a real OmegaPLM (dummy has none)."""
    inner = getattr(model, "_model", None)
    return inner is not None and hasattr(inner, "omega_plm")


class OmegaPlmScorer:
    """Weight-tied logits from the resident OmegaFold's PLM stage.

    fp32 on purpose (see module docstring): the weights stay fp32 in the
    resident wrapper even under the fp16 profile, so a plain forward is
    both the numerically safe and the honest path.
    """

    name = "omegaplm-tied"

    def __init__(self, omega_plm, device: str):
        from omegafold.utils.protein_utils import residue_constants as rc
        got = "".join(rc.restypes)
        if got != OF_RESTYPES:  # столбцы логитов привязаны к порядку словаря
            raise RuntimeError(
                f"omegafold vocab drifted: expected {OF_RESTYPES!r}, got {got!r}")
        self.plm = omega_plm
        self.device = device

    def score(self, seq: str) -> PlmScoreResult:
        import torch
        seq = validate_sequence(seq)
        t0 = time.perf_counter()
        tokens, mask = make_tokens(seq, self.device)
        # fwd_cfg обязателен (GAU безусловно разыменует subbatch_size, как и
        # в полном фолде — omegafold_model.py:88-94); PLM без recycle.
        # PLM 不循环：与完整折叠相同的 fwd_cfg 字段。
        fwd_cfg = argparse.Namespace(subbatch_size=None, num_recycle=0)
        with torch.no_grad():
            node, _edges = self.plm(tokens, mask, fwd_cfg=fwd_cfg)
            # [1, L, 1280] @ [23, 1280].T → [L, 23]; fp32 при любом профиле.
            W = self.plm.input_embedding.weight.detach().float()
            logits = node[0].detach().float() @ W.T
            # 20 канонических столбцов вендорного порядка (X/padding исключены).
            lp_of = torch.log_softmax(logits[:, :OF_X], dim=-1)

        lp = lp_of.detach().cpu().numpy().astype(np.float64)
        cols = [OF_RESIDX[aa] for aa in STD_AA]
        logprobs = lp[:, cols]  # [L, 20] в порядке STD_AA
        if not np.isfinite(logprobs).all():
            raise RuntimeError("PLM produced non-finite log-probabilities")

        margins = np.zeros_like(logprobs)
        for i, wt_aa in enumerate(seq):
            margins[i] = logprobs[i] - logprobs[i, STD_AA.index(wt_aa)]
        margins[np.arange(len(seq)), [STD_AA.index(a) for a in seq]] = 0.0

        return PlmScoreResult(
            seq=seq, logprobs=logprobs, margins=margins,
            scorer=self.name, device=self.device,
            elapsed_s=time.perf_counter() - t0)


class DummyPlmScorer:
    """Deterministic fake PLM scores (tests + UI wiring only).

    NEVER produces report numbers — the same rule as ml.folding.dummy_model.
    A seeded uniform logit table: same sequence -> identical margins, so
    the full pipeline is testable without GPU or vendored weights, and
    exp(logprobs).sum == 1 stays a checkable property.
    """

    name = "dummy-plm"

    def score(self, seq: str) -> PlmScoreResult:
        seq = validate_sequence(seq)
        t0 = time.perf_counter()
        seed = int(hashlib.sha256(f"dummy-plm:{seq}".encode()).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        logits = rng.uniform(-2.0, 2.0, size=(len(seq), len(STD_AA)))
        shifted = logits - logits.max(axis=1, keepdims=True)
        logprobs = shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))
        margins = np.zeros_like(logprobs)
        for i, wt_aa in enumerate(seq):
            margins[i] = logprobs[i] - logprobs[i, STD_AA.index(wt_aa)]
        margins[np.arange(len(seq)), [STD_AA.index(a) for a in seq]] = 0.0
        return PlmScoreResult(
            seq=seq, logprobs=logprobs, margins=margins,
            scorer=self.name, device="cpu",
            elapsed_s=time.perf_counter() - t0)

    def margin(self, pos0: int, alt_aa: str, seq: str) -> float:
        """Same signature as OmegaPlmScorer would need a seq — scores first."""
        return self.score(seq).margin(pos0, alt_aa)


def get_plm_scorer(model):
    """The scorer for the resident model: real if it has a PLM, else dummy.

    Dummy-profile runs (tests) get the fake scorer and stay GPU-free with
    the same result shape; a real profile gets the weight-tied scorer.
    """
    if has_plm(model):
        return OmegaPlmScorer(model._model.omega_plm, model.device)
    return DummyPlmScorer()