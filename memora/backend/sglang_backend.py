"""可选推理后端：SGLang 外部 server 模式（OpenAI 兼容端点）。

适用场景：用户本机已用 GPU 启动 sglang server，希望获得更高吞吐。
注意：SGLang 依赖 torch，不适合打包进离线 EXE；这里只做「连接已运行的 server」，
不负责启动/打包。EXE 默认引擎仍是 llama.cpp。

启动示例（用户侧，需自行 pip install sglang + 有 GPU）：
    python -m sglang.launch_server \\
        --model-path XHToken/Spark-X2.5-4B \\
        --host 127.0.0.1 --port 30000 --context-length 1000000
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from .base import MemoraLLM, ModelNotReadyError, strip_thinking
from .. import config
from ..log import get_logger

log = get_logger(__name__)


class SGLangBackend(MemoraLLM):
    name = "sglang"

    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = model_id or config.get_selected_model_id()
        self._llm = None

    def _model_name(self) -> str:
        if config.SGLANG_MODEL_NAME:
            return config.SGLANG_MODEL_NAME
        # 跟随选中模型（sglang 端注册名通常为仓库末段）
        return self.model_id.split("/")[-1]

    def _ensure(self) -> None:
        if self._llm is not None:
            return
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:  # pragma: no cover
            raise ModelNotReadyError(
                "未安装 langchain-openai，无法连接 SGLang server。\n"
                "请先：pip install langchain-openai"
            ) from e

        self._llm = ChatOpenAI(
            base_url=config.SGLANG_BASE_URL,
            api_key=config.SGLANG_API_KEY,
            model=self._model_name(),
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS_REVIEW,
            request_timeout=120,
            max_retries=1,
            streaming=False,
            # extra_body 透传为请求 JSON 字段，关闭 Spark 思考链，直接输出正文
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        self._ensure()
        log.debug("SGLang 推理：prompt 长度=%d，max_tokens=%s", len(prompt), max_tokens)
        llm = self._llm
        bind: dict[str, float | int] = {}
        if max_tokens is not None:
            bind["max_tokens"] = max_tokens
        if temperature is not None:
            bind["temperature"] = temperature
        if bind:
            llm = self._llm.bind(**bind)
        msg = llm.invoke([HumanMessage(content=prompt)])
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        return strip_thinking(content or "")

    def health_check(self) -> str:
        try:
            self._ensure()
            return f"SGLang 已连接：{config.SGLANG_BASE_URL}（model={self._model_name()}）"
        except Exception as e:  # noqa: BLE001
            return f"未就绪：{e}"
