#!/usr/bin/env bash
# Memora 离线依赖安装（Linux / macOS / Termux，全程无需联网）
# 用法：bash install.sh
# 可选环境变量：PYTHON=python3
set -e
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "============================================================"
echo " Memora 离线依赖安装（全程无需联网）"
echo " 平台：$(uname -s) $(uname -m)"
echo "============================================================"

if [ ! -d wheelhouse ]; then
  echo "[错误] 未找到 wheelhouse 目录。请使用完整离线发布包，"
  echo "       或在有网机器上为当前平台生成："
  echo "       $PYTHON -m pip download -r requirements-runtime.txt -d wheelhouse"
  exit 1
fi

echo "使用解释器：$PYTHON"
"$PYTHON" --version
echo
echo "正在从本地 wheelhouse 安装依赖..."
"$PYTHON" -m pip install --no-index --find-links=wheelhouse -r requirements-runtime.txt

echo
echo "============================================================"
echo " 依赖安装完成。"
echo " 1) 若尚未放置模型：把模型目录放到项目上一级 root/models，"
echo "    或启动后在「模型管理」页下载（该步骤需网络，可在有网时完成）。"
echo " 2) 运行 bash scripts/start.sh 启动，浏览器访问 http://127.0.0.1:8000"
echo "============================================================"
