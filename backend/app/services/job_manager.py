"""Job manager: SQLite-backed queue with a single-GPU worker discipline.

6 GB VRAM = one CUDA stream — GPU jobs run strictly serially behind a
threading.Semaphore(1); CPU work (alignment of host arrays, benchmarks on
CPU) goes through a small thread pool. Artifacts (PDB files, result.json)
live on disk under data/jobs/<job_id>/; SQLite stores job state for polling.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from ..config import get_settings
from .strings import stage_text

# статусы, из которых джоб уже не выйдет: отменять нечего
# 终态：任务不会再变化，无需取消
TERMINAL_STATUSES = ("done", "error", "cancelled")


class JobCancelled(Exception):
    """Кооперативная отмена: брошено из точки проверки внутри джоба.

    Поток нельзя убить снаружи, поэтому длинные циклы фолдинга сами зовут
    Job.raise_if_cancelled() перед каждым шагом, а _run переводит джоб в
    статус "cancelled", когда исключение до него долетит.
    协作式取消：从任务内部的检查点抛出。外部无法终止线程，
    因此长折叠循环在每个步骤前调用 Job.raise_if_cancelled()，
    异常抵达 _run 后任务转为 "cancelled"。
    """

    def __init__(self, job_id: str) -> None:
        super().__init__(f"job {job_id} cancelled")
        self.job_id = job_id


class Job:
    def __init__(self, job_id: str, kind: str, params: dict[str, Any]):
        self.job_id = job_id
        self.kind = kind
        self.params = params
        self.status = "queued"
        self.progress = 0.0
        self.message: str | None = None
        self.error: str | None = None
        self.result: dict[str, Any] | None = None
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.finished_at: str | None = None
        self._cancel = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    def raise_if_cancelled(self) -> None:
        """Точка проверки внутри длинных циклов (перед каждым фолдом).

        长循环内的检查点（每次折叠前）。
        """
        if self.cancelled:
            raise JobCancelled(self.job_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id, "kind": self.kind, "status": self.status,
            "progress": self.progress, "message": self.message,
            "error": self.error, "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self) -> None:
        s = get_settings()
        self.jobs_dir = s.data_dir / "jobs"
        self.gpu_sem = threading.Semaphore(1)  # один CUDA-стрим — одна задача за раз | 单 CUDA 流，一次一个任务
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job")
        self._init_db(s.db_path)

    # -- персистентность ----------------------------------------------------
    # -- 持久化 -------------------------------------------------------------
    def _init_db(self, db_path: Path) -> None:
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db_lock = threading.Lock()
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY, kind TEXT, status TEXT,
                progress REAL, params TEXT, result TEXT, error TEXT,
                created_at TEXT, finished_at TEXT)""")
        self._db.commit()

    def _persist(self, job: Job) -> None:
        with self._db_lock:
            self._db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                (job.job_id, job.kind, job.status, job.progress,
                 json.dumps(job.params),
                 json.dumps(job.result) if job.result is not None else None,
                 job.error, job.created_at, job.finished_at))
            self._db.commit()

    def update(self, job: Job) -> None:
        """Persist a stage change (progress/message) so pollers see it."""
        self._persist(job)

    # -- жизненный цикл задачи ---------------------------------------------
    # -- 任务生命周期 --------------------------------------------------------
    def submit(self, kind: str, params: dict[str, Any],
               run_fn: Callable[[Job], dict[str, Any]], use_gpu: bool) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, kind, params)
        with self._lock:
            self._jobs[job_id] = job
        self._persist(job)
        self._pool.submit(self._run, job, run_fn, use_gpu)
        return job_id

    def cancel(self, job_id: str) -> Job | None:
        """Кооперативно остановить джоб; None — джоба нет.

        Отмена ставит флаг и сразу переводит джоб в "cancelled": ожидающий
        джоб не начнётся, идущий прервётся на ближайшей точке проверки.
        Джоб, найденный только в SQLite (процесс перезапущен), флагом уже не
        остановить — но смена статуса полезна: она чистит зависшие "running"
        из истории после рестарта.
        协作式停止任务；None 表示任务不存在。取消设置标志并立即转为 "cancelled"：
        排队中的不会开始，运行中的在最近检查点中断。仅存在于 SQLite 的任务
        （进程已重启）无法用标志停止，但改状态仍可清理重启后卡住的 "running"。
        """
        job = self.get(job_id)
        if job is None:
            return None
        if job.status in TERMINAL_STATUSES:
            return job
        job.cancel()
        job.status = "cancelled"
        job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._persist(job)
        return job

    def _run(self, job: Job, run_fn: Callable[[Job], dict[str, Any]],
             use_gpu: bool) -> None:
        try:
            # отмена могла прийти, пока джоб ждал воркер в пуле
            # 任务在池中等待 worker 时可能已被取消
            job.raise_if_cancelled()
            job.status = "running"
            self._persist(job)
            if use_gpu:
                # честная обратная связь очереди: сообщаем о конкуренции до блокировки
                # 诚实的队列反馈：在阻塞前先报告资源竞争
                if not self.gpu_sem.acquire(blocking=False):
                    job.message = stage_text("gpu_wait", job.params.get("lang"))
                    self._persist(job)
                    # ожидание слота прерываемо: иначе отмена джоба, стоящего в
                    # очереди, ждала бы завершения текущего
                    # 等待槽位可中断：否则队列中任务的取消要等当前任务结束
                    while not self.gpu_sem.acquire(timeout=0.5):
                        if job.cancelled:
                            raise JobCancelled(job.job_id)
                try:
                    job.raise_if_cancelled()
                    result = run_fn(job)
                finally:
                    self.gpu_sem.release()
            else:
                job.raise_if_cancelled()
                result = run_fn(job)
            job.result = result
            job.status = "done"
            job.progress = 1.0
        except JobCancelled:
            # отдельная ветка ДО Exception: отмена — не ошибка
            # 单独分支放在 Exception 之前：取消不是错误
            job.status = "cancelled"
            job.error = None
        except Exception as exc:  # отдаём в API, воркер не падает | 上抛给 API，工作线程不崩溃
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
        finally:
            job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._persist(job)

    # -- доступ -------------------------------------------------------------
    # -- 访问器 --------------------------------------------------------------
    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        """Recent jobs for the history panel (newest first, from SQLite)."""
        with self._db_lock:
            rows = self._db.execute(
                "SELECT job_id, kind, status, params, error, created_at, "
                "finished_at FROM jobs ORDER BY created_at DESC, rowid DESC "
                "LIMIT ?", (limit,)).fetchall()
        out = []
        for job_id, kind, status, params_json, error, created, finished in rows:
            params = json.loads(params_json)
            seq: str = params.get("sequence", "")
            pos = params.get("position")
            mut_aa = params.get("mutant_aa")
            if kind == "mutate" and pos and 1 <= pos <= len(seq):
                label = f"{seq[pos - 1]}{pos}{mut_aa}"
            elif kind == "scan" and pos and 1 <= pos <= len(seq):
                label = f"{seq[pos - 1]}{pos}×19"
            elif kind == "ensemble" and pos and 1 <= pos <= len(seq):
                label = f"{seq[pos - 1]}{pos} μ{params.get('mu')}×{params.get('k')}"
            elif kind == "scan_map":
                n_pos = len(params.get("positions") or [])
                label = f"map {n_pos}×19"  # нейтрально к языку; i18n в UI | 语言中立；i18n 在 UI 中
            elif kind == "plm_screen":
                k = params.get("fold_top_k") or 0
                label = f"PLM {len(seq)}×19" + (f" top{k}" if k else "")
            elif kind == "dms_validation":
                label = f"DMS {str(params.get('assay_id'))[:24]}"
            else:
                label = f"{len(seq)} aa"
            out.append({
                "job_id": job_id, "kind": kind, "status": status,
                "label": label, "sequence": seq,
                "position": pos, "mutant_aa": mut_aa,
                # параметры ручки (ensemble; в остальных None) — UI восстанавливает
                # из них μ/τ/K/mode; seed выводится из того же конфига,
                # поэтому отдельное поле не нужно
                # 旋钮参数（ensemble；其余任务为 None）——UI 由此恢复 μ/τ/K/mode；
                # seed 由同一配置派生，无需单独字段
                "mu": params.get("mu"), "tau": params.get("tau"),
                "k": params.get("k"), "mode": params.get("mode"),
                "fold_top_k": params.get("fold_top_k") if kind == "plm_screen" else None,
                "error": error, "created_at": created, "finished_at": finished,
            })
        return out

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        with self._db_lock:
            row = self._db.execute(
                "SELECT job_id, kind, status, progress, params, result, error, "
                "created_at, finished_at FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        job = Job(row[0], row[1], json.loads(row[4]))
        job.status, job.progress, job.error = row[2], row[3], row[6]
        job.created_at, job.finished_at = row[7], row[8]
        if row[5] is not None:
            job.result = json.loads(row[5])
        return job

    def job_dir(self, job_id: str) -> Path:
        d = self.jobs_dir / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager