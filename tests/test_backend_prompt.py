"""后端对话模板包装与思考链清洗的纯函数测试。"""
from __future__ import annotations

from memora.backend.base import build_chat_prompt, strip_thinking


def test_chat_prompt_contains_spark_tokens():
    p = build_chat_prompt("你好")
    assert "<｜start▁of▁sentence｜><|User|>" in p
    assert "你好" in p
    assert "<｜end▁of▁sentence｜>" in p
    # 默认关闭思考：Bot 前缀后直接是思考结束 token
    assert "<|Bot|></think>" in p


def test_chat_prompt_enable_thinking():
    p = build_chat_prompt("你好", enable_thinking=True)
    assert "<|Bot|><think>" in p


def test_strip_thinking_ascii_markers():
    raw = "<think>先分析一下用户意图\n结论如下</think>\n## 报告\n正文内容"
    out = strip_thinking(raw)
    assert "先分析" not in out
    assert out.startswith("## 报告")
    assert "正文内容" in out


def test_strip_thinking_rendered_markers():
    raw = "[Start thinking]\n模型内心独白\n[End thinking]\n这是正文回答。"
    out = strip_thinking(raw)
    assert "内心独白" not in out
    assert "Start thinking" not in out
    assert out == "这是正文回答。"


def test_strip_thinking_plain_text_passthrough():
    raw = "## 一、核心结论\n没有任何思考标记的正文"
    assert strip_thinking(raw) == raw.strip()


def test_strip_thinking_empty():
    assert strip_thinking("") == ""


def test_runnable_accepts_prompt_value():
    """回归：PromptTemplate 之后 RunnableLambda 收到的是 StringPromptValue，
    必须先 to_string，不能直接 len()（曾报 'StringPromptValue' has no len()）。"""
    from langchain_core.prompts import PromptTemplate
    from memora.backend.base import MemoraLLM

    class FakeLLM(MemoraLLM):
        name = "fake"
        def complete(self, prompt, *, max_tokens=None, temperature=None):
            assert isinstance(prompt, str)
            return f"OK:{len(prompt)}"

    chain = PromptTemplate.from_template("问题：{q}") | FakeLLM().get_runnable()
    assert chain.invoke({"q": "你好"}) == "OK:5"
