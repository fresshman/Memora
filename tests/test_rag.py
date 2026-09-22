"""RAG 检索增强单元测试（确定性 HashEmbedder，不依赖模型/网络）。"""
from __future__ import annotations

import datetime as dt

import pytest

from memora.parsers.base import Conversation, Message
from memora.retrieval.chunker import chunk_conversation, parse_time
from memora.retrieval.index import VectorStore
from memora.retrieval.embedder import HashEmbedder
from memora.retrieval.retriever import (
    Retriever, build_retriever, compress_conversation,
    conversation_fingerprint, _skeleton_chunks, _has_strong_signal,
)


def _msg(i: int, day: int, speaker: str, text: str,
         hour: int = 9, minute: int = 0) -> Message:
    t = dt.datetime(2024, 3, day, hour, (minute + i) % 60).strftime("%Y-%m-%d %H:%M:%S")
    return Message(speaker=speaker, time=t, text=text)


def test_parse_time():
    assert parse_time("2024-03-01 09:00:00") is not None
    assert parse_time("2024/3/1 9:00") is not None
    assert parse_time(None) is None
    assert parse_time("时间未知") is None


def test_chunk_topic_split_by_gap():
    conv = Conversation(source="plain", title="t", messages=[
        _msg(0, 1, "甲", "上午的讨论", 9, 0),
        _msg(1, 1, "乙", "继续上午", 9, 5),
        _msg(2, 3, "甲", "隔了两天后的讨论", 14, 0),
    ])
    chunks = chunk_conversation(conv, max_chars=420, gap_minutes=30)
    topics = {c.topic_id for c in chunks}
    assert topics == {0, 1}


def test_chunk_covers_all_messages():
    msgs = []
    for i in range(60):
        msgs.append(_msg(i, 1 + i // 20, f"人{i % 4}",
                         f"这是第{i}条消息，包含一些业务内容用于填充篇幅" * 1,
                         9 + (i // 8), i))
    conv = Conversation(source="plain", title="t", messages=msgs)
    chunks = chunk_conversation(conv, max_chars=200, overlap_msgs=2, gap_minutes=999999)
    # 首末消息索引必须被覆盖（不丢开头/结尾）
    assert min(c.start_idx for c in chunks) == 0
    assert max(c.end_idx for c in chunks) == len(msgs) - 1
    # 每条消息的独特标记至少出现在某个块中
    joined = "\n".join(c.text for c in chunks)
    assert "第0条消息" in joined and f"第{len(msgs) - 1}条消息" in joined


def test_chunk_respects_budget_for_short_messages():
    msgs = [_msg(i, 1, f"人{i % 3}", "短内容" * 20, 9, i) for i in range(40)]
    conv = Conversation(source="plain", title="t", messages=msgs)
    chunks = chunk_conversation(conv, max_chars=300, overlap_msgs=1, gap_minutes=999999)
    # 由多条短消息组成的块不应远超预算（允许少量行余量）
    for c in chunks:
        assert len(c.text) <= 300 + 120


def _long_conv_with_early_buried(n_noise=120):
    """开头埋一条关键待办，其后大量噪声，结尾再来一条（时间严格单调递增）。"""
    start = dt.datetime(2024, 3, 1, 8, 30)
    msgs = [
        Message(speaker="王强", time=start.strftime("%Y-%m-%d %H:%M:%S"),
                text="我负责安全审计报告，截止时间是下周五下班前，这是客户特别强调的待办事项"),
    ]
    noise = [
        "刚才在楼下便利店买了瓶水，排队的人比想象中要多一些",
        "午休的时候看了会儿手机，外面阳光挺好适合出去走走",
        "这个话题咱们有空再聊，先把手头日常的琐碎事情处理完吧",
        "打印机旁边的纸箱快满了，等会儿路过顺手带下去扔掉",
        "周末打算去公园转转，听说最近湖边花开得还不错可以拍照",
        "工位上的绿植该浇水了，叶片看着有点发蔫，不太有精神",
        "食堂今天的例汤有点咸，喝了两口就放下了，口味不太习惯",
        "下班路上慢一点，雨天路滑，骑车的同事记得放慢一些速度",
        "刚才群里消息有点多，往上翻了半天才看到前面聊的内容",
        "茶水间的微波炉用完记得清理，下一个同事还要接着热饭",
    ]
    speakers = ["甲", "乙", "丙", "丁"]
    for i in range(n_noise):
        t = start + dt.timedelta(minutes=7 * (i + 1))
        msgs.append(Message(speaker=speakers[i % 4],
                            time=t.strftime("%Y-%m-%d %H:%M:%S"),
                            text=noise[i % len(noise)]))
    t_end = start + dt.timedelta(minutes=7 * (n_noise + 1))
    msgs.append(Message(speaker="李娜", time=t_end.strftime("%Y-%m-%d %H:%M:%S"),
                        text="最终决定：上线窗口定在下下周一凌晨两点，由运维张伟负责发布"))
    return Conversation(source="wechat", title="长群", messages=msgs)


def test_retrieval_finds_early_buried_todo():
    conv = _long_conv_with_early_buried()
    assert conv.char_count > 3000
    emb = HashEmbedder()
    retr = build_retriever(conv, emb, use_cache=False)
    ctx = retr.retrieve_qa(emb, "谁负责安全审计报告？截止时间是什么时候？",
                          char_budget=4000, top_k=10)
    assert "安全审计报告" in ctx.context_text
    assert "下周五" in ctx.context_text
    assert ctx.mode == "rag"


def test_retrieval_review_skeleton_and_facets():
    conv = _long_conv_with_early_buried()
    emb = HashEmbedder()
    retr = build_retriever(conv, emb, use_cache=False)
    ctx = retr.retrieve_review(emb, char_budget=5000)
    # 骨架应保住时间线：开头埋点与结尾决定都在
    assert "安全审计报告" in ctx.context_text
    assert "上线窗口" in ctx.context_text
    assert len(ctx.context_text) <= 5200


def test_compress_fallback_covers_early_and_late():
    conv = _long_conv_with_early_buried()
    ctx = compress_conversation(conv, char_budget=3000)
    assert ctx.mode == "compressed"
    # 旧版直接砍头会丢这条；结构化压缩必须保住开头关键信息
    assert "安全审计报告" in ctx.context_text
    assert "上线窗口" in ctx.context_text


def test_skeleton_prefers_signal_chunks():
    conv = Conversation(source="plain", title="t", messages=[
        Message(speaker="甲", time="2024-03-01 09:00:00", text="早"),
        Message(speaker="乙", time="2024-03-01 09:01:00", text="嗯"),
        Message(speaker="丙", time="2024-03-01 09:05:00",
                text="这里有个风险：第三方限流没确认，可能导致延期上线"),
    ])
    chunks = chunk_conversation(conv, max_chars=420, gap_minutes=999999)
    skel = _skeleton_chunks(chunks)
    joined = " ".join(c.text for c in skel)
    assert "风险" in joined and "限流" in joined


def test_strong_signal_rejects_uncertain_smalltalk():
    # 含信号词但语气未决 / 寒暄，不应进高置信骨架
    assert not _has_strong_signal("这个需求我们再看看，等领导拍板，回头再细化")
    assert not _has_strong_signal("等需求明确了我们再评估工作量，现在信息不全")
    assert not _has_strong_signal("相关文档我有空补，最近排期满")
    assert not _has_strong_signal("今天天气不错，中午一起吃饭吗")
    # 明确的风险 / 决定 / 承诺必须命中
    assert _has_strong_signal("第三方支付接口限流没确认，可能导致上线延期")
    assert _has_strong_signal("那就定了，预算控制在五万，超了重新审批")
    assert _has_strong_signal("安全审计报告我负责，截止下周五下午六点前")
    assert _has_strong_signal("生产服务器证书下周到期，不续网站会打不开")


def test_fingerprint_stable_and_sensitive():
    conv = _long_conv_with_early_buried(20)
    fp1 = conversation_fingerprint(conv, 420, 2, 30, "m")
    fp2 = conversation_fingerprint(conv, 420, 2, 30, "m")
    assert fp1 == fp2
    conv.messages[5].text = "被修改过的内容XYZ"
    fp3 = conversation_fingerprint(conv, 420, 2, 30, "m")
    assert fp3 != fp1


def test_vector_store_save_load(tmp_path):
    conv = _long_conv_with_early_buried(40)
    emb = HashEmbedder()
    chunks = chunk_conversation(conv)
    store = VectorStore.build(chunks, emb)
    store.save(tmp_path)
    loaded = VectorStore.load(tmp_path)
    assert loaded.index.ntotal == store.index.ntotal
    qv = emb.embed(["安全审计报告 截止 负责"])[0]
    hit_orig = store.search(qv, 3)
    hit_load = loaded.search(qv, 3)
    assert hit_orig[0][0].chunk_id == hit_load[0][0].chunk_id


def test_system_messages_excluded_from_chunks():
    conv = Conversation(source="wechat", title="t", messages=[
        Message(speaker="系统", time="2024-03-01 08:00:00",
                text="张三 撤回了一条消息", kind="system"),
        Message(speaker="张三", time="2024-03-01 09:00:00",
                text="正经的业务结论：预算五万"),
    ])
    chunks = chunk_conversation(conv)
    joined = " ".join(c.text for c in chunks)
    assert "撤回" not in joined
    assert "预算五万" in joined


def test_review_context_hard_cap_under_dense_signals():
    """信号词异常密集时，复盘 RAG 上下文也不得超过模型安全输入（硬红线）。

    回归：强信号块曾豁免字符预算，逐条都含风险词的超长会话会让上下文膨胀到
    5 万+ 字，直接撑爆 llama-server 上下文（400 exceed_context_size）。
    """
    from memora import config
    start = dt.datetime(2024, 3, 1, 8, 0)
    risk_words = ["延期", "阻塞", "故障", "限流", "缺货", "到期", "中断", "回滚"]
    msgs = [
        Message(speaker="负责人", time=start.strftime("%Y-%m-%d %H:%M:%S"),
                text="最终决定：本次正式上线日期定为11月8日，所有人按此排期"),
    ]
    for i in range(700):
        t = start + dt.timedelta(minutes=5 * (i + 1))
        w = risk_words[i % len(risk_words)]
        msgs.append(Message(
            speaker=f"人{i % 5}", time=t.strftime("%Y-%m-%d %H:%M:%S"),
            text=f"第{i}项进展：这里存在{w}风险，可能影响本次交付，需要持续跟进处理情况"))
    t_end = start + dt.timedelta(minutes=5 * 701)
    msgs.append(Message(speaker="收尾人", time=t_end.strftime("%Y-%m-%d %H:%M:%S"),
                        text="我负责在上线前完成全链路压测报告，截止本周五下班前提交"))
    conv = Conversation(source="wechat", title="密集信号长群", messages=msgs)
    assert conv.char_count > config.MAX_INPUT_CHARS  # 前提：原文确实超长

    emb = HashEmbedder()
    retr = build_retriever(conv, emb, use_cache=False)
    ctx = retr.retrieve_review(emb)
    # 硬红线：喂给模型的上下文绝不超过安全输入长度
    assert len(ctx.context_text) <= config.MAX_INPUT_CHARS, (
        f"上下文 {len(ctx.context_text)} 超过安全输入 {config.MAX_INPUT_CHARS}")
    # 头部决定（强信号、时间序最先）必须保留
    assert "11月8日" in ctx.context_text
    # 尾部待办靠头/尾锚点预留保留
    assert "压测报告" in ctx.context_text
