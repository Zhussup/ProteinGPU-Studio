"""Folding service: one resident model per process, lazily created.

Holds the FoldingModel singleton (real OmegaFold when weights+CUDA are
available, DummyModel otherwise) plus the WT FoldingCache. Model access is
guarded by the JobManager's GPU semaphore upstream — this layer assumes it
is called from a GPU-slot-protected context.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "ml"),):
    if p not in sys.path:
        sys.path.insert(0, p)

from ml.folding.base import FoldingModel, PredictResult  # noqa: E402

from ..config import get_settings  # noqa: E402
from .cache import FoldingCache  # noqa: E402


class FoldingService:
    def __init__(self) -> None:
        self._model: FoldingModel | None = None
        self._lock = threading.Lock()
        self._profile_override: str | None = None  # set via set_profile()
        s = get_settings()
        self.cache = FoldingCache(maxsize=s.wt_cache_size)

    @property
    def profile(self) -> str:
        return self._profile_override or get_settings().folding_profile

    def set_profile(self, profile: str) -> None:
        """Switch the resident model to a requested profile.

        Must be called from a serialized context (the job GPU semaphore):
        the current model is closed and rebuilt lazily on next use. The WT
        cache keys on model name, so different profiles reuse nothing —
        that is correct: different precision = different weights in memory.
        """
        with self._lock:
            if self.profile == profile:
                return
            if self._model is not None:
                self._model.close()
                self._model = None
            self._profile_override = profile

    @property
    def model(self) -> FoldingModel:
        with self._lock:
            if self._model is None:
                from ml.folding.dummy_model import get_model
                self._model = get_model(self.profile)
            return self._model

    @property
    def model_name(self) -> str:
        return self.model.name

    def predict_cached(self, seq: str) -> tuple[PredictResult, bool]:
        """Fold or reuse. Returns (result, from_cache)."""
        name = self.model_name
        hit = self.cache.get(seq, name)
        if hit is not None:
            return hit, True
        res = self.model.predict(seq)
        self.cache.put(seq, res, name)
        return res, False

    def close(self) -> None:
        with self._lock:
            if self._model is not None:
                self._model.close()
                self._model = None


_service: FoldingService | None = None


def get_folding_service() -> FoldingService:
    global _service
    if _service is None:
        _service = FoldingService()
    return _service