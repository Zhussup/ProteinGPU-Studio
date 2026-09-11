"""WT folding cache: sha1(sequence) → PredictResult, LRU-bounded.

A mutation job folds WT + mutant; when several mutations of the same protein
run back to back (the demo does exactly that), the WT fold is reused instead
of paying the GPU inference again.
"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any


class FoldingCache:
    def __init__(self, maxsize: int = 128) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(seq: str, model_name: str = "") -> str:
        return hashlib.sha1(f"{model_name}:{seq}".encode()).hexdigest()

    def get(self, seq: str, model_name: str = ""):
        k = self.key(seq, model_name)
        with self._lock:
            if k in self._store:
                self._store.move_to_end(k)
                self.hits += 1
                return self._store[k]
            self.misses += 1
            return None

    def put(self, seq: str, value: Any, model_name: str = "") -> None:
        k = self.key(seq, model_name)
        with self._lock:
            self._store[k] = value
            self._store.move_to_end(k)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"size": len(self._store), "hits": self.hits, "misses": self.misses}