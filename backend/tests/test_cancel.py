"""Кооперативная отмена задач — без GPU.

Отмена в этом проекте кооперативная (поток нельзя убить снаружи), поэтому
проверяем три вещи: флаг действительно бросает в точке проверки; идущий цикл
прерывается по нему; джоб, стоящий в очереди за GPU-слотом, отменяется, не
дожидаясь освобождения слота. HTTP-слой проверяется на 404/409 — сценарий
«отменить идущий» на dummy-модели был бы гонкой (задача успевает завершиться
раньше запроса).

协作式任务取消——无需 GPU。取消是协作式的（外部无法终止线程），
因此验证三件事：标志确实在检查点抛出；运行中的循环会被中断；
排队等待 GPU 槽位的任务无需等槽位释放即可取消。
HTTP 层验证 404/409——“取消运行中任务”在 dummy 模型上会是竞态。
"""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ml"))
sys.path.insert(0, str(REPO / "hpc_core" / "python"))

os.environ["PGS_FOLDING_PROFILE"] = "dummy"
_tmp = Path(__file__).parent / "_testdata_cancel"
_tmp.mkdir(exist_ok=True)
os.environ["PGS_DATA_DIR"] = str(_tmp)
os.environ["PGS_DB_PATH"] = str(_tmp / "jobs.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import get_settings  # noqa: E402

get_settings.cache_clear()
import backend.app.services.job_manager as jm_mod  # noqa: E402
import backend.app.services.folding_service as fs_mod  # noqa: E402

jm_mod._manager = None      # свежий JobManager на изолированной БД | 在隔离数据库上新建 JobManager
fs_mod._service = None      # свежий FoldingService | 新建 FoldingService

from backend.app.main import app  # noqa: E402
from backend.app.services.job_manager import (  # noqa: E402
    Job, JobCancelled, get_job_manager,
)
from backend.app.services.strings import stage_text  # noqa: E402

client = TestClient(app)

SHORT = "ACDEFGHIKL"  # ровно 10 aa | 恰好 10 aa


class TestCancellationFlag:
    def test_clean_job_does_not_raise(self):
        job = Job("t-clean", "unit", {})
        assert not job.cancelled
        job.raise_if_cancelled()  # не бросает, пока джоб не отменён | 未取消时不抛出

    def test_cancelled_job_raises_at_checkpoint(self):
        job = Job("t-cancel", "unit", {})
        job.cancel()
        assert job.cancelled
        with pytest.raises(JobCancelled):
            job.raise_if_cancelled()


class TestManagerCancellation:
    def test_cancel_stops_a_running_loop(self):
        jm = get_job_manager()
        started, stopped = threading.Event(), threading.Event()

        def run_fn(job: Job) -> dict:
            started.set()
            try:
                for _ in range(2000):  # ~20 с, если отмена не сработает
                    job.raise_if_cancelled()
                    time.sleep(0.01)
            finally:
                stopped.set()
            return {}

        job_id = jm.submit("slow", {"lang": "ru"}, run_fn, use_gpu=False)
        assert started.wait(5.0), "джоб не стартовал"
        jm.cancel(job_id)
        # остановку доказывает ИМЕННО выход из run_fn: статус cancelled
        # выставляет и сам cancel(), поэтому по нему отмену не отличить
        # 证明停止的是 run_fn 的退出：cancelled 状态由 cancel() 本身设置
        assert stopped.wait(5.0), "цикл не прервался по флагу"

        job = jm.get(job_id)
        assert job.status == "cancelled"
        assert job.error is None, "отмена — не ошибка"
        assert job.finished_at is not None
        # история (GET /jobs) читает статус из SQLite — отмена обязана туда доехать
        # 历史（GET /jobs）从 SQLite 读状态——取消必须写入
        rows = client.get("/api/v1/jobs").json()
        assert any(r["job_id"] == job_id and r["status"] == "cancelled" for r in rows)

    def test_cancel_while_waiting_for_gpu_slot(self):
        """Джоб в очереди за слотом отменяется сразу, а не после освобождения."""
        jm = get_job_manager()
        started = threading.Event()

        def run_fn(job: Job) -> dict:
            started.set()
            return {}

        jm.gpu_sem.acquire()  # держим единственный слот | 占住唯一槽位
        try:
            job_id = jm.submit("gpu", {"lang": "ru"}, run_fn, use_gpu=True)
            for _ in range(300):  # ждём, пока _run упрётся в занятый слот
                if jm.get(job_id).message == stage_text("gpu_wait", "ru"):
                    break
                time.sleep(0.02)
            assert jm.get(job_id).message == stage_text("gpu_wait", "ru")

            jm.cancel(job_id)
            for _ in range(300):
                if jm.get(job_id).status == "cancelled":
                    break
                time.sleep(0.02)

            assert jm.get(job_id).status == "cancelled", "слот всё ещё занят — отмена ждала его"
            assert not started.is_set(), "run_fn не должен был начаться"
        finally:
            jm.gpu_sem.release()


class TestCancelEndpoint:
    def test_unknown_job_404(self):
        r = client.post("/api/v1/jobs/no-such-job/cancel")
        assert r.status_code == 404

    def test_cancel_finished_job_409(self):
        r = client.post("/api/v1/predict", json={"sequence": SHORT})
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]
        for _ in range(300):  # задача завершается быстро, но не мгновенно
            if client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "done":
                break
            time.sleep(0.1)
        assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "done"

        r = client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert r.status_code == 409, "завершённый джоб отменять поздно"


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    import shutil
    shutil.rmtree(_tmp, ignore_errors=True)
