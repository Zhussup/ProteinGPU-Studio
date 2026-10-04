#!/usr/bin/env bash
# dev.sh — поднять бэкенд и фронтенд одной командой (dev-режим).
# Бэкенд: uvicorn из .venv на порту 8077 (его же ждёт прокси vite.config.ts).
# Фронтенд: vite с SPA-fallback (BrowserRouter) на первом свободном порту от 5173.
# Ctrl+C гасит оба процесса; логи — в .dev/backend.log и .dev/frontend.log.
# dev.sh —— 一条命令同时启动后端和前端（开发模式）。
# 后端：使用 .venv 中的 uvicorn 监听 8077（vite.config.ts 的代理正是此端口）。
# 前端：vite 带 SPA 回退（BrowserRouter），从 5173 起取第一个空闲端口。
# Ctrl+C 会同时关闭两个进程；日志位于 .dev/backend.log 与 .dev/frontend.log。
set -euo pipefail
cd "$(dirname "$0")"

BACK_PORT=8077          # должен совпадать с proxy.target в frontend/vite.config.ts
FRONT_BASE=5173
HOST=127.0.0.1
START_BACKEND=1
LOG_DIR=.dev
BACK_PID=""; FRONT_PID=""

usage() {
  cat <<'EOF'
Использование: ./dev.sh [опции]

  -b, --backend-port PORT   порт бэкенда (по умолчанию 8077;
                            при смене поправьте proxy.target в frontend/vite.config.ts)
  -f, --frontend-port PORT  стартовый порт фронтенда (по умолчанию 5173;
                            если занят — берётся следующий свободный)
      --host HOST           хост обоих серверов (по умолчанию 127.0.0.1)
      --no-backend          не поднимать бэкенд (уже запущен вручную)
  -h, --help                эта справка
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -b|--backend-port)  BACK_PORT="${2:?нужен порт}"; shift 2 ;;
    -f|--frontend-port) FRONT_BASE="${2:?нужен порт}"; shift 2 ;;
    --host)             HOST="${2:?нужен хост}"; shift 2 ;;
    --no-backend)       START_BACKEND=0; shift ;;
    -h|--help)          usage; exit 0 ;;
    *) echo "dev.sh: неизвестная опция «$1» (см. ./dev.sh --help)" >&2; exit 2 ;;
  esac
done

# Свободен ли порт: сначала ss, иначе /dev/tcp (порт-хост без утилит).
# 端口是否空闲：优先用 ss，否则回退到 /dev/tcp。
port_busy() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
  else
    (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null && { exec 3>&-; return 0; }
    return 1
  fi
}

cleanup() {
  trap - INT TERM HUP EXIT
  echo
  echo "[dev] останавливаю…"
  # гасим группу процессов целиком (npm → vite, uvicorn → воркеры);
  # если группа недоступна (чужой pgid) — бьём по дереву процессов
  # 关闭整个进程组（npm → vite、uvicorn → 子进程）；
  # 若无法按进程组关闭（pgid 变了），则按进程树逐个结束
  local pid
  for pid in "$FRONT_PID" "$BACK_PID"; do
    [ -n "$pid" ] || continue
    kill -- "-$pid" 2>/dev/null || { kill "$pid" 2>/dev/null; pkill -P "$pid" 2>/dev/null; }
  done
  wait 2>/dev/null || true
  echo "[dev] готово."
}
trap cleanup INT TERM HUP EXIT

# --- предполётная проверка: venv, node_modules --------------------------------
[ -d .venv ] || { echo "[dev] нет .venv — сначала ./scripts/00_setup_env.sh" >&2; exit 1; }
if [ ! -d frontend/node_modules ]; then
  echo "[dev] нет frontend/node_modules — сначала: cd frontend && npm install" >&2
  exit 1
fi
mkdir -p "$LOG_DIR"

# --- бэкенд ------------------------------------------------------------------
if [ "$START_BACKEND" = 1 ]; then
  if port_busy "$BACK_PORT"; then
    if curl -fsS -m 3 "http://${HOST}:${BACK_PORT}/api/v1/health" >/dev/null 2>&1; then
      # порт занят, но это живой наш бэкенд — второй не поднимаем
      # 端口被占用但确为本项目后端——不再启动第二个
      echo "[dev] бэкенд уже слушает :${BACK_PORT} — переиспользую его"
      START_BACKEND=0
    else
      echo "[dev] порт ${BACK_PORT} занят чужим процессом — освободите его или задайте --backend-port" >&2
      exit 1
    fi
  fi
fi

if [ "$START_BACKEND" = 1 ]; then
  echo "[dev] бэкенд  → http://${HOST}:${BACK_PORT}  (лог: ${LOG_DIR}/backend.log)"
  setsid .venv/bin/uvicorn backend.app.main:app --host "$HOST" --port "$BACK_PORT" \
    >"$LOG_DIR/backend.log" 2>&1 &
  BACK_PID=$!

  # ждём /api/v1/health, но не бесконечно: модель грузится лениво при первом запросе
  # 轮询 /api/v1/health，但不无限等待：模型在首个请求时才惰性加载
  ok=0
  for _ in $(seq 1 60); do
    if curl -fsS -m 2 "http://${HOST}:${BACK_PORT}/api/v1/health" >/dev/null 2>&1; then ok=1; break; fi
    kill -0 "$BACK_PID" 2>/dev/null || break
    sleep 0.5
  done
  if [ "$ok" = 1 ]; then
    echo "[dev] бэкенд отвечает: $(curl -fsS -m 2 "http://${HOST}:${BACK_PORT}/api/v1/health")"
  else
    echo "[dev] бэкенд не ответил за 30 с — смотрите ${LOG_DIR}/backend.log (запускаю фронтенд дальше)" >&2
  fi
fi

# --- фронтенд ----------------------------------------------------------------
FRONT_PORT="$FRONT_BASE"
while port_busy "$FRONT_PORT"; do
  echo "[dev] порт ${FRONT_PORT} занят — пробую $((FRONT_PORT + 1))"
  FRONT_PORT=$((FRONT_PORT + 1))
  [ "$FRONT_PORT" -gt $((FRONT_BASE + 20)) ] && { echo "[dev] нет свободного порта рядом с ${FRONT_BASE}" >&2; exit 1; }
done

# с --host 0.0.0.0 показываем localhost: к 0.0.0.0 браузером не ходят
# 当 --host 为 0.0.0.0 时显示 localhost：浏览器不会访问 0.0.0.0
if [ "$HOST" = "0.0.0.0" ]; then FRONT_URL="http://localhost:${FRONT_PORT}"; else FRONT_URL="http://${HOST}:${FRONT_PORT}"; fi
echo "[dev] фронтенд → ${FRONT_URL}  (лог: ${LOG_DIR}/frontend.log)"
# --host задаём явно: без него vite слушает только localhost/[::1], и 127.0.0.1 мимо
# 显式指定 --host：否则 vite 仅监听 localhost/[::1]，127.0.0.1 会落空
setsid npm --prefix frontend run dev -- --port "$FRONT_PORT" --strictPort --host "$HOST" \
  >"$LOG_DIR/frontend.log" 2>&1 &
FRONT_PID=$!

sleep 1.5
if ! kill -0 "$FRONT_PID" 2>/dev/null; then
  echo "[dev] фронтенд не поднялся — хвост лога:" >&2
  tail -n 20 "$LOG_DIR/frontend.log" >&2 || true
  exit 1
fi

echo
echo "[dev] всё поднято. Ctrl+C — остановить оба. Логи: ${LOG_DIR}/"
echo "[dev] открывайте ${FRONT_URL}/structure"
wait || true
