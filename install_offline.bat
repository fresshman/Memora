@echo off
chcp 65001 >nul
cd /d %~dp0
setlocal
if "%PYTHON%"=="" set PYTHON=python

echo ============================================================
echo  Memora 离线依赖安装（全程无需联网）
echo ============================================================
echo.

if not exist "wheelhouse" (
  echo [错误] 未找到 wheelhouse 目录。请使用完整离线发布包，
  echo        或在有网机器先运行 scripts\build_offline.ps1 生成。
  pause
  exit /b 1
)

echo 使用解释器：%PYTHON%
"%PYTHON%" --version
echo.
echo 正在从本地 wheelhouse 安装依赖...
"%PYTHON%" -m pip install --no-index --find-links=wheelhouse -r requirements-runtime.txt
if errorlevel 1 (
  echo.
  echo [错误] 依赖安装失败。请确认 Python 版本为 3.10-3.12 且与打包机同为 64 位 Windows。
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  依赖安装完成。
echo  1) 若尚未放置模型，请把模型目录放到项目上一级 root\models，
echo     或启动后在「模型管理」页下载（该步骤需要网络，可在有网时完成）。
echo  2) 双击 start.bat（或 scripts\start.bat）启动，浏览器访问
echo     http://127.0.0.1:8000
echo ============================================================
pause
endlocal
