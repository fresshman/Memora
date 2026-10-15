#!/usr/bin/env bash
# Memora 一键启动（Linux / macOS / Termux，端侧离线单端口）
# 用法：bash scripts/start.sh   （也可 ./scripts/start.sh，需可执行权限）
# 可选环境变量：PYTHON=python3  MEMORA_PORT=8000
set -e

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
PORT="${MEMORA_PORT:-8000}"

echo "============================================================"
echo " Memora 一键启动（端侧离线 · 单端口）"
echo " 平台：$(uname -s) $(uname -m)  解释器：$PYTHON"
echo "============================================================"

echo "[1/2] 环境自检..."
"$PYTHON" scripts/doctor.py || {
  echo
  echo "自检发现缺失项，仍尝试启动（若失败请按提示修复）。"
}

echo "[2/2] 启动后端  http://127.0.0.1:${PORT}"

open_browser() {
  local url="http://127.0.0.1:${PORT}"
  if [ ! -f web/out/index.html ]; then
    echo "未构建静态前端：开发模式请 cd web && npm run dev（前端 http://localhost:3000）"
    return
  fi
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1 || true
  elif command -v termux-open-url >/dev/null 2>&1; then termux-open-url "$url" >/dev/null 2>&1 || true
  else echo "请用浏览器访问 $url"; fi
}

# 后端就绪后再打开浏览器（后台延迟执行，不影响前端主进程）
( sleep 5; open_browser ) &

# 前台运行后端：Ctrl+C 信号直接传给 uvicorn，优雅关闭并释放模型
exec "$PYTHON" -m uvicorn server.main:app --host 127.0.0.1 --port "$PORT"
