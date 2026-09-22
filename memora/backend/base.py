"""推理后端统一抽象。

目标：让上层 LangChain 智能体只依赖 `complete(prompt)` 或 `get_runnable()`，
不关心底层是 llama.cpp 内嵌还是 SGLang 外部 server。

本模块同时提供 Spark-X2.5 官方对话模板包装与思考链清洗工具，
保证「指令任务」拿到的是干净正文而不是思维链（模型默认开启 thinking）。
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Iterator

# Spark-X2.5 chat template（取自模型 GGUF 内嵌 chat_template.jinja）
# 注意：｜为全角竖线 U+FF5C，▁ 为 U+2581，不可替换成普通字符。
_SOT = "<｜start▁of▁sentence｜>"
_EOT = "<｜end▁of▁sentence｜>"
_DEFAULT_SYSTEM = "you are a helpful assistant."

# llama.cpp 把思考特殊 token 渲染为 [Start thinking]/[End thinking]；
# 部分部署则直接输出 <think>/</think>，两类都处理。
_THINK_END_MARKERS = ["</think>", "[End thinking]", "[end thinking]"]
_THINK_BLOCK_RE = re.compile(
    r"\s*\[Start thinking\].*?(?:\[End thinking\]\s*)?",
    re.IGNORECASE | re.DOTALL,
)


def build_chat_prompt(user_content: str, system: str | None = None,
                      enable_thinking: bool = False) -> str:
    """按 Spark-X2.5 官方 chat template 包装单轮用户请求（补全接口用）。

    enable_thinking=False 时在 Bot 前缀后直接给思考结束 token，
    引导模型跳过思维链、直接输出正文。
    """
    sys_text = system or _DEFAULT_SYSTEM
    parts = [
        f"{_SOT}<|System|>\n{sys_text}{_EOT}",
        f"{_SOT}<|User|>\n{user_content}{_EOT}",
        f"{_SOT}<|Bot|>" + ("<think>" if enable_thinking else "</think>"),
    ]
    return "\n".join(parts)


def strip_thinking(text: str) -> str:
    """剥离模型输出中的思维链，返回正文。

    - 有思考结束标记：取最后一个结束标记之后的内容；
    - 只有 [Start thinking] 块：整块删除；
    - 没有任何思考标记：原样返回。
    """
    if not text:
        return ""
    cuts = [text.rfind(m) + len(m) for m in _THINK_END_MARKERS if m in text]
    if cuts:
        text = text[max(cuts):]
    text = _THINK_BLOCK_RE.sub("", text, count=1)
    return text.strip()


class ModelNotReadyError(RuntimeError):
    """模型或推理后端未就绪时抛出，携带给用户的修复指引。"""


class MemoraLLM(ABC):
    """统一推理接口。"""

    name: str = "base"

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """执行一次补全，返回纯文本。"""
        raise NotImplementedError

    def stream_complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """流式补全，逐段 yield 正文增量。

        默认实现退化为一次性返回（不支持真流式的后端可直接复用）；
        llama.cpp 后端覆写为基于 SSE 的真流式。依赖服务端关闭思考链
        （chat_template_kwargs.enable_thinking=False），故增量即正文。
        """
        yield self.complete(prompt, max_tokens=max_tokens, temperature=temperature)

    def get_runnable(self, max_tokens: int | None = None,
                     temperature: float | None = None):
        """返回 LangChain Runnable，输入 prompt 字符串，输出文本。

        max_tokens/temperature 在构造 Runnable 时绑定，便于复盘链与问答链
        使用不同的生成长度。懒加载 langchain_core，避免未安装时拖累启动。
        """
        from langchain_core.runnables import RunnableLambda

        def _invoke(prompt_value):
            # PromptTemplate 之后传入的是 StringPromptValue，需先转纯文本
            text = prompt_value.to_string() if hasattr(prompt_value, "to_string") \
                else str(prompt_value)
            return self.complete(
                text, max_tokens=max_tokens, temperature=temperature
            )

        return RunnableLambda(_invoke, name=f"{self.name}-complete")

    def close(self) -> None:
        """释放后端占用的外部资源（如本地推理子进程）。默认无动作。"""

    def health_check(self) -> str:
        """返回就绪状态描述，供 UI 展示。"""
        return f"{self.name} 后端已就绪"
