@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0..

echo ============================================================
echo  Memora 一键启动（端侧离线 · 单端口）
echo ============================================================

REM 可在此文件所在目录上层放 run_env.bat 自定义 PYTHON / 端口等
if exist "%~dp0run_env.bat" call "%~dp0run_env.bat"
if "%PYTHON%"=="" set PYTHON=python

echo [1/2] 环境自检...
"%PYTHON%" scripts\doctor.py
if errorlevel 1 (
  echo.
  echo 自检发现缺失项，仍可尝试启动？按 Ctrl+C 退出并修复，或
  pause
)

echo [2/2] 启动后端  http://127.0.0.1:8000
start "Memora" cmd /k "chcp 65001 >nul && cd /d %CD% && %PYTHON% -m uvicorn server.main:app --host 127.0.0.1 --port 8000"

timeout /t 4 /nobreak >nul

if exist "web\out\index.html" (
  echo.
  echo 检测到静态前端，进入单端口离线模式，正在打开浏览器...
  start "" http://127.0.0.1:8000
  echo 浏览器访问 http://127.0.0.1:8000 即可，首次推理会自动拉起本地模型。
) else (
  echo.
  echo 未构建静态前端，改用开发模式（需 Node.js）：前端 http://localhost:3000
  cd web
  if not exist node_modules (
    echo 首次运行，安装前端依赖...
    call npm install
  )
  start "Memora Web" cmd /k "chcp 65001 >nul && cd /d %CD% && npm run dev"
  timeout /t 6 /nobreak >nul
  start "" http://localhost:3000
)
endlocal
