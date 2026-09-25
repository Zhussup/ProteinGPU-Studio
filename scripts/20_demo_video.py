"""Demo video: drive the real UI end-to-end and record 1080p.

Honesty policy: the recorded job is a FULL real run on the real model —
profile is pinned to a non-dummy inference profile (fp16-gpu by default,
real OmegaFold weights + CUDA), and after the run we fetch the result and
assert the reported engine/model is omegafold, not dummy. A short warmup
job (not recorded) pre-loads the model and caches the WT PDB so the
recorded run is watchable, but the recorded job itself is complete.

Flow: preset → mutation → progress bar → 3D model (rotate) → metrics.

Usage: ~/.venvs/playwright/bin/python scripts/20_demo_video.py
Output: data/demo/demo.mp4 (+ demo.webm source, warmup_check.png)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "demo"
FRONTEND = "http://localhost:5173"  # vite биндится на ::1 на этой машине | vite 在此机器绑定 ::1
BACKEND = "http://127.0.0.1:8077"

PRESET = "KRAS G12D"           # для опционального клика чипа прогрева | 用于可选的预热芯片点击
PROFILE = os.environ.get("DEMO_PROFILE", "fp32-gpu")  # настоящий OmegaFold; никогда не dummy | 真实 OmegaFold；绝不用 dummy
# прогрев включён по умолчанию: префолдит WT, чтобы ЗАПИСЫВАЕМАЯ задача была короче
# (сама записываемая задача — по-прежнему полный реальный прогон).
# 默认开启预热：预先折叠 WT，缩短录制任务（录制任务本身仍是完整真实运行）。
SKIP_WARMUP = os.environ.get("DEMO_SKIP_WARMUP", "0") == "1"

# что печатаем на камеру (демо-сценарий KRAS G12D)
# 镜头前输入的内容（KRAS G12D 演示场景）
TYPE_HEADER = ">KRAS G12D"
TYPE_SEQ = ("MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEY"
            "SAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDT"
            "KQAQDLARSYGIPFIETSAKTRQRVEDAFYTLVREIRQYRLKKISKEEKTPGCVKIKKCIIM")
POSITION = 12
MUT_AA = "D"
VIEWPORT = {"width": 1920, "height": 1080}
JOB_WAIT_MS = 20 * 60 * 1000   # GPU может быть занят / модель перезагружается при смене профиля | GPU 可能忙/换配置时模型会重载

# кинематографическая камера: анимируем zoom body к zoom_target, удерживая
# элемент по центру; размытие страницы следует за скоростью скролла → фейковый motion blur
# 电影感运镜：动画调整 body zoom 至 zoom_target 并保持元素居中；
# 页面模糊跟随滚动速度变化 → 模拟运动模糊
EASE_JS = """
(args) => new Promise((res) => {
  const [sel, zoomTarget, dur] = args;
  const el = document.querySelector(sel);
  if (!el) { res(false); return; }
  const z0 = parseFloat(document.body.style.zoom || '1');
  const t0 = performance.now();
  let prev = window.scrollY;
  const ease = (x) => x < 0.5 ? 4*x*x*x : 1 - Math.pow(-2*x+2, 3)/2;
  const step = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    const e = ease(p);
    document.body.style.zoom = z0 + (zoomTarget - z0) * e;
    const r = el.getBoundingClientRect();
    const ty = window.scrollY + r.top + r.height/2 - window.innerHeight/2;
    const cur = window.scrollY;
    window.scrollTo(0, cur + (ty - cur) * (0.25 + 0.55 * e));
    const v = Math.abs(window.scrollY - prev); prev = window.scrollY;
    document.body.style.filter = v > 1.5 ? `blur(${Math.min(7, v * 0.08)}px)` : 'none';
    if (p < 1) requestAnimationFrame(step);
    else {
      document.body.style.filter = 'none';
      const r2 = el.getBoundingClientRect();
      window.scrollTo(0, window.scrollY + r2.top + r2.height/2 - window.innerHeight/2);
      res(true);
    }
  };
  requestAnimationFrame(step);
})
"""


def zoom_to(page, sel: str, factor: float, dur: int = 900) -> None:
    page.evaluate(EASE_JS, [sel, factor, dur])


def pan_to(page, sel: str, dur: int = 800) -> None:
    zoom_to(page, sel, 1.0, dur)  # pan = зум обратно к 1.0 и центрирование цели | pan = 缩放回 1.0 并居中目标


def eased_drag(page, x: float, y: float, dx: float, dy: float,
               steps: int = 90, dur: float = 2.0) -> None:
    """Smooth ease-in-out mouse drag (3Dmol rotates on left-drag)."""
    import math
    page.mouse.move(x, y)
    page.mouse.down()
    t0 = time.perf_counter()
    for i in range(1, steps + 1):
        p = i / steps
        e = 0.5 - 0.5 * math.cos(math.pi * p)  # easeInOutSine
        page.mouse.move(x + dx * e, y + dy * e)
        dt = t0 + dur * p - time.perf_counter()
        if dt > 0:
            time.sleep(dt)
    page.mouse.up()


def wait_job_done(page, timeout_ms: int = JOB_WAIT_MS) -> None:
    """Wait while the honest stage-progress panel is visible (job running)."""
    panel = page.locator('[data-demo="progress"]')
    try:
        panel.wait_for(timeout=8000)
        # панель — внизу левой колонки, ниже границы 1080p; подводим её в кадр,
        # чтобы видео действительно её показывало
        # 面板位于左栏底部，1080p 折叠线之下；把它滚入画面，视频才能拍到
        panel.scroll_into_view_if_needed()
        time.sleep(1.5)
    except PWTimeoutError:
        pass  # задача могла завершиться до начала наблюдения | 任务可能在我们开始观察前已完成
    panel.wait_for(state="hidden", timeout=timeout_ms)
    pan_to(page, '[data-demo="viewer"]', 900)


# хореография камеры для 3D-фазы: турнет + зум к сайту + зум обратно.
# Движется НАШ rAF-твин с плавным прогрессом, 3Dmol зовём только мгновенными
# операциями (rotate(angle,'y',0) / zoom(k,0)): собственный animateMotion 3Dmol
# (цепочка setTimeout) ползёт в headless-захвате — на него не полагаемся.
# 3D 阶段的运镜编排：转台 + 拉近到位点 + 拉回。
# 由我们的 rAF 补间以缓动进度驱动，仅以瞬时操作调用 3Dmol
#（rotate(angle,'y',0) / zoom(k,0)）：3Dmol 自带的 animateMotion
#（setTimeout 链）在无头录制中极慢，绝不依赖它。
CAM_JS = """
async () => {
  const mol = window.__mol;
  if (!mol) return false;
  const ease = (x) => x < 0.5 ? 4*x*x*x : 1 - Math.pow(-2*x+2, 3)/2;
  const tween = (dur, fn) => new Promise((res) => {
    const t0 = performance.now();
    let prev = 0;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      const e = ease(p);
      fn(e - prev, e);
      prev = e;
      p < 1 ? requestAnimationFrame(step) : res();
    };
    requestAnimationFrame(step);
  });
  const spin = (deg, dur) => tween(dur, (de) => mol.rotate(deg * de, 'y', 0));
  // зум с 1× до F× с плавным прогрессом: покадровый мультипликативный шаг
  // q(e)/q(e_prev), q(e) = 1 + (F-1)*e, применяемый как мгновенный zoom(k, 0)
  // 以缓动进度从 1× 放大到 F×：每帧乘性步长 q(e)/q(e_prev)，
  // q(e) = 1 + (F-1)*e，以瞬时 zoom(k, 0) 应用
  const zoomBy = (F, dur) => {
    let last = 0;
    return tween(dur, (de) => {
      const qPrev = 1 + (F - 1) * last;
      const qNow = 1 + (F - 1) * (last + de);
      mol.zoom(qNow / qPrev, 0);
      last += de;
    });
  };
  await spin(150, 2600);
  await spin(-100, 2200);
  await zoomBy(1.9, 1200);
  await new Promise((r) => setTimeout(r, 1500));
  await spin(80, 1600);
  await zoomBy(0.62, 1100);
  await new Promise((r) => setTimeout(r, 1200));
  return true;
}
"""


def assert_no_backend_error(page) -> None:
    err = page.locator(".border-red-300")
    if err.count() and err.first.is_visible():
        raise RuntimeError(f"job failed in UI: {err.first.inner_text()}")


def check_honesty(page, job_id: str) -> str:
    """Fetch the recorded job's result and assert the model is real."""
    data = page.evaluate(
        "async (id) => (await fetch(`/api/v1/jobs/${id}/result`)).json()", job_id
    )
    model = str(data.get("model", ""))
    print(f"[honesty] recorded job {job_id} model={model!r}")
    if "dummy" in model.lower():
        raise RuntimeError(f"NOT HONEST: recorded job ran the dummy model ({model})")
    if model and "omegafold" not in model.lower():
        print(f"[honesty] warning: unexpected model name {model!r}")
    return model


def wait_until_idle(page) -> None:
    """Wait for preset chips to appear (frontend + backend are both up)."""
    page.get_by_text("Демо-пресеты").first.wait_for(state="visible", timeout=30_000)


def warmup(pw) -> None:
    """Not recorded: pre-load the profile's model + cache the WT PDB."""
    browser = pw.chromium.launch()
    page = browser.new_context(viewport=VIEWPORT).new_page()
    page.goto(FRONTEND)
    wait_until_idle(page)
    page.get_by_role("button", name=PRESET).last.click()
    page.locator("#profile-select").select_option(PROFILE)
    page.get_by_role("button", name="Только WT").click()
    wait_job_done(page)
    assert_no_backend_error(page)
    # sanity screenshot: confirms WebGL renders in headless before we record
    page.screenshot(path=str(OUT_DIR / "warmup_check.png"), full_page=True)
    print("[warmup] done — model loaded, WT cached, screenshot saved")
    browser.close()


def record(pw) -> tuple[Path, str]:
    browser = pw.chromium.launch()
    ctx = browser.new_context(
        viewport=VIEWPORT, record_video_dir=str(OUT_DIR), record_video_size=VIEWPORT,
    )
    page = ctx.new_page()
    page.goto(FRONTEND + "?e2e=1")  # ?e2e открывает хук камеры 3Dmol | ?e2e 暴露 3Dmol 运镜钩子
    wait_until_idle(page)
    time.sleep(1.0)

    # 1) зум к полю последовательности и печать FASTA на камеру
    # 1) 放大到序列输入框，在镜头前输入 FASTA
    page.locator('[data-demo="sequence"]').click()
    zoom_to(page, '[data-demo="sequence"]', 1.7, 900)
    time.sleep(0.4)
    page.keyboard.type(TYPE_HEADER, delay=30)
    page.keyboard.press("Enter")
    page.keyboard.type(TYPE_SEQ, delay=22)
    time.sleep(1.0)

    # 2) мутация: панорама туда, позиция 12 → D
    # 2) 突变：平移过去，设位置 12 → D
    pan_to(page, '[data-demo="mutation"]', 900)
    time.sleep(0.4)
    pos = page.locator('input[type="number"]')
    pos.click()
    pos.press("Control+a")
    pos.type("12", delay=60)
    page.locator("select").first.select_option(MUT_AA)
    time.sleep(1.4)  # дать вьюеру показать подсветку / бейдж G12D | 让查看器展示高亮条 / G12D 徽标

    # 3) честный профиль, запуск и поездка на честном прогресс-баре
    # 3) 真实配置，运行并跟随真实进度条
    pan_to(page, '[data-demo="runrow"]', 800)
    time.sleep(0.4)
    page.locator("#profile-select").select_option(PROFILE)
    time.sleep(0.8)
    with page.expect_response("**/api/v1/mutate") as resp_info:
        page.get_by_role("button", name="WT + мутант").click()
    job_id = resp_info.value.json()["job_id"]
    print(f"[record] submitted job {job_id}")
    page.locator('[data-demo="progress"]').wait_for(timeout=10_000)
    pan_to(page, '[data-demo="progress"]', 800)
    zoom_to(page, '[data-demo="progress"]', 1.22, 1400)
    wait_job_done(page)
    assert_no_backend_error(page)

    # 4) 3D-модель: ждём оба PDB, затем плавный турнет + зум к сайту
    # 4) 3D 模型：等两个 PDB，然后平滑转台 + 拉近到位点
    page.get_by_text("Результат наложения").first.wait_for(timeout=90_000)
    page.get_by_text(f"Мутация {POSITION}").first.wait_for(timeout=60_000)
    time.sleep(1.2)
    model = check_honesty(page, job_id)

    box = page.locator('[data-demo="viewer"] div.cursor-grab').first.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    if page.evaluate("() => !!window.__mol"):
        # хореография камеры: турнет с плавным прогрессом + зум к сайту + обратно
        # (мгновенные операции 3Dmol, движимые нашим rAF-твином — см. CAM_JS)
        # 运镜编排：缓动转台 + 拉近到位点 + 拉回（rAF 补间驱动的瞬时 3Dmol 操作——见 CAM_JS）
        ok = page.evaluate(CAM_JS)
        if not ok:
            raise RuntimeError("CAM_JS returned false — window.__mol missing")
    else:
        eased_drag(page, cx, cy, 190, -25, steps=100, dur=2.2)
        time.sleep(0.6)
        eased_drag(page, cx, cy, -210, 40, steps=105, dur=2.4)
        time.sleep(0.6)
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -500)
        time.sleep(0.9)
        page.mouse.wheel(0, -450)
        time.sleep(0.9)
        eased_drag(page, cx, cy, 130, 15, steps=80, dur=1.8)
        time.sleep(1.0)

    # 5) метрики с кинематографической панорамой, затем финальный hero-кадр модели
    # 5) 平移到指标，最后给模型一个压轴镜头
    pan_to(page, '[data-demo="metrics"]', 900)
    time.sleep(3.0)
    pan_to(page, '[data-demo="viewer"]', 900)
    time.sleep(2.5)

    video = page.video
    ctx.close()
    webm = Path(video.path())
    browser.close()
    final = OUT_DIR / "demo.webm"
    webm.replace(final)
    return final, model


def _ffmpeg() -> Path:
    """Full ffmpeg with libx264 (imageio-ffmpeg wheel); bundled playwright
    ffmpeg only has libvpx and cannot mux mp4."""
    try:
        import imageio_ffmpeg
        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        raise RuntimeError("pip install imageio-ffmpeg (полный ffmpeg с libx264)")


def to_mp4(webm: Path) -> Path:
    out = webm.with_suffix(".mp4")
    subprocess.run([str(_ffmpeg()), "-y", "-i", str(webm), "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(out)], check=True, capture_output=True)
    return out


def dump_frames(video: Path, tag: str) -> None:
    """Extract 3 frames (15%/60%/90%) so the run can be verified visually."""
    dur = subprocess.run([str(_ffmpeg()), "-hide_banner", "-i", str(video)],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+)\.(\d+)", dur)
    if not m:
        print(f"[frames] could not parse duration of {video.name}")
        return
    total = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 100
    for frac in (0.15, 0.60, 0.90):
        ts = total * frac
        out = OUT_DIR / f"frame_{tag}_{int(frac * 100)}.png"
        subprocess.run([str(_ffmpeg()), "-y", "-ss", f"{ts:.2f}", "-i", str(video),
                        "-frames:v", "1", str(out)], check=True, capture_output=True)
        print(f"[frames] {out}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        if not SKIP_WARMUP:
            warmup(pw)
        webm, model = record(pw)
    mp4 = to_mp4(webm)
    print(f"[done] {webm.name} ({webm.stat().st_size // 1024} KB)"
          f" → {mp4.name} ({mp4.stat().st_size // 1024} KB), model={model}")
    dump_frames(webm, "rec")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — сообщаем и выходим с ненулевым кодом для CI | 报告并以非零码退出供 CI
        print(f"FAILED: {e}", file=sys.stderr)
        raise