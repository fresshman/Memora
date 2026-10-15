"""默认推理后端：本机 llama-server 子进程 + OpenAI 兼容接口。

为什么不用 llama-cpp-python 进程内绑定：
  Spark2_5 架构 2026-09-06 才合入 llama.cpp，PyPI 上的 llama-cpp-python
  发布版内置的 llama.cpp 往往滞后，加载 GGUF 会报
  “unknown model architecture: 'spark2_5'”。
  llama.cpp 官方每日构建（b110xx）直接提供 llama-server 可执行文件，
  免编译、免 Python 绑定，解压即可用，并天然提供 OpenAI 兼容的
  /v1/chat/completions。本后端负责：
    1. 自动发现 llama-server 可执行文件；
    2. 选中模型后在本机随机空闲端口拉起子进程（127.0.0.1，仅本机可达）；
    3. 轮询 /health 等待模型加载完成；
    4. 通过 langchain-openai 以 OpenAI 协议推理，关闭 Spark 思考链；
    5. 进程退出/切换模型时终止子进程。

离线分发：把官方每日构建 zip（如 llama-b11046-bin-win-cpu-x64.zip）解压到
  Memora/tools/llamacpp/bin/  或项目同级  ../llama.cpp/build/bin/，
也可用环境变量 MEMORA_LLAMASERVER_PATH 显式指定 llama-server 路径。
"""
from __future__ import annotations

import atexit
import ctypes
import ctypes.wintypes  # noqa: F401  显式导入，否则 ctypes.wintypes 属性不存在
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .base import MemoraLLM, ModelNotReadyError, strip_thinking
from .. import config
from ..log import get_logger

log = get_logger(__name__)

_EXE = "llama-server.exe" if sys.platform == "win32" else "llama-server"


def posix_preexec():
    """POSIX 子进程钩子：父进程死亡时内核向子进程发 SIGTERM，避免孤儿。

    与 Windows 作业对象等价；仅在非 win32 平台使用，失败静默（不影响启动）。
    同时 setpgrp 使子进程独立成组，便于整组终止。
    """
    import ctypes as _ct
    import signal as _sig

    def _hook():  # pragma: no cover - 仅 POSIX 子进程内执行
        try:
            os.setpgrp()
        except Exception:  # noqa: BLE001
            pass
        try:
            _libc = _ct.CDLL("libc.so.6", use_errno=True)
            _libc.prctl(1, _sig.SIGTERM, 0, 0, 0)  # PR_SET_PDEATHSIG=1
        except Exception:  # noqa: BLE001
            pass

    return _hook


# ---------------------------------------------------------------------------
# Windows 作业对象：父进程（后端）被强杀/崩溃时，作业内 llama-server 子进程
# 由操作系统自动终止，避免孤儿推理进程常驻内存。句柄生命周期 = 本 Python 进程。
# ---------------------------------------------------------------------------
_win32_job = None


def _get_win32_job():
    global _win32_job
    if sys.platform != "win32" or _win32_job is not None:
        return _win32_job
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = ctypes.wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.wintypes.LPVOID, ctypes.wintypes.LPCWSTR]
        k32.SetInformationJobObject.restype = ctypes.wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [
            ctypes.wintypes.HANDLE, ctypes.c_int,
            ctypes.wintypes.LPVOID, ctypes.wintypes.DWORD,
        ]
        k32.AssignProcessToJobObject.restype = ctypes.wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [
            ctypes.wintypes.HANDLE, ctypes.wintypes.HANDLE,
        ]

        class _BasicLimit(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.wintypes.DWORD),
                ("SchedulingClass", ctypes.wintypes.DWORD),
            ]

        class _IOCounters(ctypes.Structure):
            _fields_ = [(f"_reserved_{i}", ctypes.c_int64) for i in range(6)]

        class _ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimit),
                ("IoInfo", _IOCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        handle = k32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(f"CreateJobObjectW 失败：{ctypes.get_last_error()}")
        # 实测在已处于作业中的进程（常见于终端/IDE 启动）下，
        # BasicLimitInformation(class=2) 会报 INVALID_PARAMETER(87)，
        # ExtendedLimitInformation(class=9) 可正常设置 KILL_ON_JOB_CLOSE。
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(
            handle, 9,  # JobObjectExtendedLimitInformation
            ctypes.byref(info), ctypes.sizeof(info),
        )
        if not ok:
            raise OSError(f"SetInformationJobObject 失败：{ctypes.get_last_error()}")
        _win32_job = (k32, handle)
        log.debug("已创建 Windows 作业对象（父进程退出时自动回收 llama-server）")
    except Exception as e:  # noqa: BLE001
        log.warning("创建 Windows 作业对象失败（不影响功能，但强杀后端可能残留进程）：%s", e)
        _win32_job = False
    return _win32_job


def _assign_process_to_job(proc: subprocess.Popen) -> None:
    job = _get_win32_job()
    if sys.platform == "win32" and job:
        k32, handle = job
        ok = k32.AssignProcessToJobObject(handle, int(proc._handle))
        if not ok:
            log.warning("llama-server 加入作业对象失败（错误码 %s），强杀后端时可能残留进程",
                        ctypes.get_last_error())


def find_llama_server(explicit: str | None = None) -> Path | None:
    """按优先级查找 llama-server 可执行文件，找不到返回 None。"""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if config.LLAMACPP_SERVER_PATH:
        candidates.append(Path(config.LLAMACPP_SERVER_PATH))

    # MEMORA_LLAMACPP_PATH 可能指向仓库根、build 或 build/bin
    if config.LLAMACPP_PATH:
        p = Path(config.LLAMACPP_PATH)
        candidates += [p / _EXE, p / "bin" / _EXE, p / "build" / "bin" / _EXE]

    # 离线包推荐位置与开发布局
    candidates += [
        config.PROJECT_ROOT / "tools" / "llamacpp" / "bin" / _EXE,
        config.PROJECT_ROOT / "tools" / "llama.cpp" / "build" / "bin" / _EXE,
        config.PROJECT_ROOT / "llama.cpp" / "build" / "bin" / _EXE,
        config.PROJECT_ROOT.parent / "llama.cpp" / "build" / "bin" / _EXE,
    ]
    for c in candidates:
        if c.is_file():
            return c
    on_path = shutil.which("llama-server")
    return Path(on_path) if on_path else None


def pick_free_port() -> int:
    """让操作系统分配一个空闲端口。"""
    if config.LLAMACPP_SERVER_PORT:
        return config.LLAMACPP_SERVER_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _server_install_hint() -> str:
    if sys.platform == "win32":
        pkg = "llama-b11046-bin-win-cpu-x64.zip"
        compile_hint = "cmake -B build; cmake --build build --config Release"
    elif sys.platform == "darwin":
        pkg = "llama-b11046-bin-macos-arm64.zip"
        compile_hint = "cmake -B build; cmake --build build"
    else:
        pkg = "llama-b11046-bin-ubuntu-x64.zip"
        compile_hint = "cmake -B build; cmake --build build"
    return (
        "未找到 llama-server 可执行文件。Spark2_5 架构需 2026-09-07 之后的 llama.cpp：\n"
        "  方式一（推荐，免编译）：到 https://github.com/ggml-org/llama.cpp/releases\n"
        f"  下载当前平台最新每日构建（如 {pkg}），解压到\n"
        f"  {config.PROJECT_ROOT / 'tools' / 'llamacpp' / 'bin'}\n"
        "  （国产麒麟/统信 + x86_64 海光/兆芯 CPU 用 ubuntu-x64 版；ARM Linux 用 *-arm64 版）\n"
        "  方式二：设置环境变量 MEMORA_LLAMASERVER_PATH 指向 llama-server 可执行文件。\n"
        f"  方式三：自行编译最新 llama.cpp（{compile_hint}）后放到 ../llama.cpp/build/bin。"
    )


class LlamaCppBackend(MemoraLLM):
    """本机 llama-server 子进程后端（对上层暴露统一 complete 接口）。"""

    name = "llamacpp"

    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = model_id or config.get_selected_model_id()
        self._proc: subprocess.Popen | None = None
        self._port: int | None = None
        self._exe: Path | None = None
        self._model_path: str | None = None
        self._llm = None
        self._log_fh = None
        self._stopping = False
        # 初始思考档位（快速 / 深度），来自配置；运行时可切换
        self.set_thinking_enabled(config.THINKING_MODE == "deep")

    # ------------------------------------------------------------------
    def _build_cmd(self, exe: Path, gguf: Path, port: int) -> list[str]:
        cmd = [
            str(exe),
            "-m", str(gguf),
            "--host", "127.0.0.1",
            "--port", str(port),
            "-c", str(config.LLAMACPP_N_CTX),
            "-ngl", str(config.LLAMACPP_N_GPU_LAYERS),
            "--cache-type-k", config.LLAMACPP_KV_QUANT,
            "--cache-type-v", config.LLAMACPP_KV_QUANT,
        ]
        if config.LLAMACPP_N_THREADS and config.LLAMACPP_N_THREADS > 0:
            cmd += ["-t", str(config.LLAMACPP_N_THREADS)]
        if config.LLAMACPP_VERBOSE:
            cmd += ["--verbose"]
        return cmd

    def _wait_health(self, port: int, timeout: int) -> None:
        url = f"http://127.0.0.1:{port}/health"
        deadline = time.time() + timeout
        last_err = ""
        while time.time() < deadline:
            # 子进程已提前退出：立即失败并给出日志尾部
            if self._proc is not None and self._proc.poll() is not None:
                tail = self._read_log_tail()
                raise ModelNotReadyError(
                    f"llama-server 启动后立即退出（返回码 {self._proc.returncode}）。\n"
                    f"命令：{' '.join(self._build_cmd(self._exe or Path('?'), Path(self._model_path or '?'), port))}\n"
                    f"日志尾部：\n{tail}"
                )
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
                last_err = str(e)
            time.sleep(1.0)
        tail = self._read_log_tail()
        raise ModelNotReadyError(
            f"等待 llama-server 就绪超时（{timeout}s，端口 {port}）。{last_err}\n日志尾部：\n{tail}"
        )

    def _read_log_tail(self, chars: int = 2000) -> str:
        try:
            log_file = config.DATA_DIR / "logs" / "llama-server.log"
            if log_file.exists():
                text = log_file.read_text(encoding="utf-8", errors="replace")
                return text[-chars:]
        except OSError:
            pass
        return "（无日志）"

    # ------------------------------------------------------------------
    def _ensure(self) -> None:
        if self._llm is not None:
            return

        # 1) 确保有可用 GGUF（离线模式缺失时直接给指引，不联网）
        from ..model_fetch import ensure_gguf
        try:
            gguf = ensure_gguf(model_id=self.model_id,
                               llamacpp_path=config.LLAMACPP_PATH or None)
        except RuntimeError as e:
            raise ModelNotReadyError(f"模型未就绪：\n{e}") from e
        self._model_path = str(gguf)

        # 2) 发现 llama-server
        exe = find_llama_server()
        if exe is None:
            raise ModelNotReadyError(_server_install_hint())
        self._exe = exe

        # 3) 拉起子进程
        port = pick_free_port()
        cmd = self._build_cmd(exe, gguf, port)
        log_dir = config.DATA_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "llama-server.log"
        self._log_fh = open(log_file, "ab", buffering=0)
        self._log_fh.write(f"\n{'=' * 60}\n启动：{' '.join(cmd)}\n{'=' * 60}\n".encode("utf-8"))
        creationflags = 0
        preexec_fn = None
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            # Linux/mac：父进程死亡时子进程收到 SIGTERM，避免孤儿
            preexec_fn = posix_preexec()
        log.info("启动本地 llama-server：%s（端口 %d，n_ctx=%d，KV=%s，GPU层=%d）",
                 exe.name, port, config.LLAMACPP_N_CTX,
                 config.LLAMACPP_KV_QUANT, config.LLAMACPP_N_GPU_LAYERS)
        self._proc = subprocess.Popen(
            cmd,
            stdout=self._log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            preexec_fn=preexec_fn,
        )
        # 加入作业对象：后端进程被强杀时 llama-server 自动陪葬
        _assign_process_to_job(self._proc)
        self._port = port
        atexit.register(self.close)

        # 4) 等待模型加载完成
        t0 = time.time()
        self._wait_health(port, config.SERVER_BOOT_TIMEOUT)
        log.info("llama-server 就绪：%s，模型 %s（加载耗时 %.1fs）",
                 f"http://127.0.0.1:{port}", gguf.name, time.time() - t0)

        # 5) OpenAI 兼容客户端
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:  # pragma: no cover
            self.close()
            raise ModelNotReadyError(
                "未安装 langchain-openai，请先：pip install langchain-openai"
            ) from e
        # CPU 长文本复盘可能耗时数分钟；本地服务不重试，避免重复长请求
        self._llm = ChatOpenAI(
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="EMPTY",
            model="memora-local",
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS_REVIEW,
            request_timeout=900,
            max_retries=0,
            # streaming=True：.stream() 真正按 token 流式（SSE 逐块）；
            # .invoke() 仍会聚合后一次性返回完整结果，行为等价。
            streaming=True,
            # extra_body 透传为请求 JSON 字段，llama-server 据此渲染 chat 模板
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

    # ------------------------------------------------------------------
    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        enable_thinking: bool | None = None,
    ) -> str:
        self._ensure()
        n = max_tokens or config.MAX_TOKENS_REVIEW
        thinking = (enable_thinking if enable_thinking is not None
                    else self.thinking_enabled)
        log.debug("llama-server 推理：prompt 长度=%d，max_tokens=%d，思考=%s",
                  len(prompt), n, thinking)
        # 每次请求按当前思考档位透传 chat_template_kwargs（覆盖默认 extra_body）
        bind: dict = {
            "extra_body": {"chat_template_kwargs":
                           {"enable_thinking": bool(thinking)}},
        }
        if max_tokens is not None:
            bind["max_tokens"] = max_tokens
        if temperature is not None:
            bind["temperature"] = temperature
        llm = self._llm.bind(**bind)
        try:
            from langchain_core.messages import HumanMessage
            msg = llm.invoke([HumanMessage(content=prompt)])
        except Exception as e:  # 子进程崩溃时给出可诊断信息
            if self._proc is not None and self._proc.poll() is not None:
                raise ModelNotReadyError(
                    f"llama-server 进程已退出（返回码 {self._proc.returncode}），"
                    f"请查看日志 data/logs/llama-server.log。原始错误：{e}"
                ) from e
            raise
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        # 深度思考也在服务端剥离思维链，只把干净正文返回给结构化链路
        return strip_thinking(content or "")

    # ------------------------------------------------------------------
    def stream_complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        enable_thinking: bool | None = None,
    ):
        """流式补全：逐 token yield 增量（SSE）。

        快速模式（服务端关闭思考链）增量即正文；
        深度模式（开启思考链）增量先包含思维块、再到正文，原样透传给前端做
        「思考过程」折叠展示，最终由 agent 在 done 时 strip_thinking 取干净正文。
        """
        self._ensure()
        n = max_tokens or config.MAX_TOKENS_REVIEW
        thinking = (enable_thinking if enable_thinking is not None
                    else self.thinking_enabled)
        log.debug("llama-server 流式推理：prompt 长度=%d，max_tokens=%d，思考=%s",
                  len(prompt), n, thinking)
        bind: dict = {
            "extra_body": {"chat_template_kwargs":
                           {"enable_thinking": bool(thinking)}},
        }
        if max_tokens is not None:
            bind["max_tokens"] = max_tokens
        if temperature is not None:
            bind["temperature"] = temperature
        llm = self._llm.bind(**bind)
        try:
            from langchain_core.messages import HumanMessage
            stream = llm.stream([HumanMessage(content=prompt)])
            for chunk in stream:
                c = chunk.content
                if isinstance(c, list):
                    c = "".join(
                        b.get("text", "") if isinstance(b, dict) else str(b) for b in c
                    )
                elif not isinstance(c, str):
                    c = str(c)
                if c:
                    yield c
        except Exception as e:  # 子进程崩溃时给出可诊断信息
            if self._proc is not None and self._proc.poll() is not None:
                raise ModelNotReadyError(
                    f"llama-server 进程已退出（返回码 {self._proc.returncode}），"
                    f"请查看日志 data/logs/llama-server.log。原始错误：{e}"
                ) from e
            raise

    # ------------------------------------------------------------------
    def close(self) -> None:
        """终止 llama-server 子进程（切换模型/应用退出时调用）。"""
        if self._stopping:
            return
        self._stopping = True
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            log.info("关闭本地 llama-server（端口 %s，PID %s）", self._port, proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        if self._log_fh is not None:
            try:
                self._log_fh.close()
            except OSError:
                pass
            self._log_fh = None
        self._llm = None
        self._stopping = False

    # ------------------------------------------------------------------
    def health_check(self) -> str:
        # 轻量检查：不启动进程，只看模型文件与二进制是否就位
        from ..model_fetch import check_model_local
        if self._proc is not None and self._proc.poll() is None and self._llm is not None:
            return f"llama.cpp 已加载 {self.model_id}（127.0.0.1:{self._port}）"
        try:
            local = check_model_local(self.model_id)
        except Exception:  # noqa: BLE001
            local = {"status": "missing"}
        exe = find_llama_server()
        if exe is None:
            return "llama.cpp：未找到 llama-server 可执行文件（见 README 安装每日构建）"
        if local["status"] == "ready":
            gguf = Path(local["gguf"] or "")
            return f"llama.cpp 就绪：{gguf.name}，推理时自动启动 server"
        if local["status"] == "downloaded":
            return f"llama.cpp：{self.model_id} 仅有 safetensors，需转换为 GGUF 或改下载官方 GGUF"
        if config.ENFORCE_OFFLINE:
            return f"llama.cpp：本地未找到 {self.model_id}（离线模式，请先在联网机下载官方 GGUF）"
        return f"llama.cpp：本地未找到 {self.model_id}，可在「模型管理」页下载"
