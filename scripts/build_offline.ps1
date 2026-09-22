# ============================================================================
#  Memora 离线发布包构建脚本（在【有网络】的打包机上执行一次）
#  产物：release\Memora（应用 + 静态前端 + 离线 wheelhouse），可整体拷贝到
#        完全断网的 Windows 机器，运行 install_offline.bat 后 start.bat 即用。
#
#  用法：
#    powershell -ExecutionPolicy Bypass -File scripts\build_offline.ps1
#    powershell -ExecutionPolicy Bypass -File scripts\build_offline.ps1 -IncludeModels
#
#  说明：
#    - 前端在本机用 Node 构建为纯静态文件（web/out），最终用户机器无需 Node；
#    - Python 依赖下载到 wheelhouse（faiss-cpu / numpy / cryptography 等含平台
#      二进制 wheel），因此【打包机与目标机应为同为 64 位 Windows、Python 3.10-3.12】；
#    - 模型体积大（4B/1.7B/bge 合计约 4GB），默认不打入包内；加 -IncludeModels
#      才会复制 root\models，否则请在目标机有网时于「模型管理」页下载，或手动拷贝。
# ============================================================================
[CmdletBinding()]
param(
  [string]$ReleaseDir = "",
  [switch]$IncludeModels,
  [switch]$SkipWheel,
  [switch]$SkipWeb
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }

$releaseBase = Join-Path $root "release"
$rel = if ($ReleaseDir) { $ReleaseDir } else { Join-Path $releaseBase "Memora" }

function Assert-Ok($msg) {
  if ($LASTEXITCODE -ne 0) { throw "$msg（退出码 $LASTEXITCODE）" }
}
function Robo($src, $dst, $extra) {
  & robocopy $src $dst /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP @extra | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy 失败：$src -> $dst（$LASTEXITCODE）" }
}

Write-Host "== [1/4] 构建静态前端（web/out） ==" -ForegroundColor Cyan
if ($SkipWeb) {
  Write-Host "  已跳过（-SkipWeb）"
} else {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "未找到 npm（Node.js）。请安装 Node 18+ 后重试，或用 -SkipWeb 跳过前端构建。"
  }
  Push-Location (Join-Path $root "web")
  try {
    if (-not (Test-Path "node_modules")) {
      Write-Host "  安装前端依赖 npm ci ..."
      & npm ci; Assert-Ok "npm ci"
    }
    # 静态包必须使用同源相对 API 路径（交由 FastAPI 单端口托管）。
    # .env.local 是开发模式指向 8000 的配置，构建期会被内联，故临时移走，
    # 让代码里的默认值（空字符串 = 同源相对）生效；构建后无论成败都恢复。
    $envLocal = Join-Path (Get-Location) ".env.local"
    $envBak = Join-Path (Get-Location) ".env.local.devbak"
    $moved = $false
    if (Test-Path $envLocal) {
      if (Test-Path $envBak) { Remove-Item $envBak -Force }
      Rename-Item $envLocal ".env.local.devbak"
      $moved = $true
    }
    try {
      Remove-Item Env:\NEXT_PUBLIC_API_BASE -ErrorAction SilentlyContinue
      & npm run build; Assert-Ok "npm run build"
    } finally {
      if ($moved -and (Test-Path $envBak)) {
        Rename-Item $envBak ".env.local"
      }
    }
  } finally { Pop-Location }
  if (-not (Test-Path (Join-Path $root "web\out\index.html"))) {
    throw "前端构建未产出 web\out\index.html"
  }
}

Write-Host "== [2/4] 下载 Python 离线依赖到 wheelhouse ==" -ForegroundColor Cyan
if ($SkipWheel) {
  Write-Host "  已跳过（-SkipWheel）"
} else {
  & $py -m pip download -r requirements-runtime.txt -d wheelhouse; Assert-Ok "pip download"
}

Write-Host "== [3/4] 组装发布目录：$rel ==" -ForegroundColor Cyan
if (Test-Path $rel) { Remove-Item $rel -Recurse -Force }
New-Item -ItemType Directory -Force -Path $rel | Out-Null

$excludeDirs = @("__pycache__", ".git", "node_modules", ".next", "data",
                 "release", ".pytest_cache", "logs", "index", "results")
foreach ($d in @("memora", "server", "scripts", "samples", "tools", "tests", "evals")) {
  if (Test-Path (Join-Path $root $d)) {
    Robo (Join-Path $root $d) (Join-Path $rel $d) @("/XD", $excludeDirs, "/XF", "*.pyc")
  }
}
if (Test-Path (Join-Path $root "web\out")) {
  Robo (Join-Path $root "web\out") (Join-Path $rel "web\out") @("/XF", "*.map")
}
foreach ($f in @("requirements.txt", "requirements-runtime.txt", ".env.example", "install_offline.bat")) {
  Copy-Item (Join-Path $root $f) (Join-Path $rel $f) -Force
}
# 发布包根目录放一键启动脚本
Copy-Item (Join-Path $root "scripts\start.bat") (Join-Path $rel "start.bat") -Force
if (-not $SkipWheel -and (Test-Path (Join-Path $root "wheelhouse"))) {
  Robo (Join-Path $root "wheelhouse") (Join-Path $rel "wheelhouse") @()
}

Write-Host "== [4/4] 模型 ==" -ForegroundColor Cyan
$modelsSrc = Join-Path $root "..\root\models"
if ($IncludeModels) {
  $modelsDst = Join-Path (Split-Path $rel) "root\models"
  if (Test-Path $modelsSrc) {
    Robo $modelsSrc $modelsDst @()
    Write-Host "  已随包复制模型到 $modelsDst"
  } else {
    Write-Warning "未找到模型目录 $modelsSrc，已跳过。"
  }
} else {
  Write-Host "  未打入模型（默认）。目标机可在有网时于「模型管理」页下载，"
  Write-Host "  或手动把 $($modelsSrc) 拷贝到发布目录同级的 root\models。"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " 离线发布包已生成：$rel" -ForegroundColor Green
Write-Host " 断网机器使用：解压 -> install_offline.bat -> 放置模型 -> start.bat" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
