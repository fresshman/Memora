"""微信聊天记录解析（.txt 导出）。

微信 PC 端导出格式示例：
    "项目群" 的聊天记录
    ===============
    2024/3/1 周五
    "张三" 2024-01-01 10:00:00
    消息内容第一行
    消息内容第二行（同一人续行）
    "李四" 2024-01-01 10:01:00
    [图片]

兼容：带引号 / 不带引号的消息头、GBK 编码、群系统消息（撤回、入群、
打招呼、日期分隔行）、图片语音文件等占位消息。
"""
from __future__ import annotations

import re

from .base import Conversation, Message
from .encoding import read_text

# 带引号消息头："发言人" 2024-01-01 10:00:00
HEAD_QUOTED_RE = re.compile(
    r'^"([^"\n]{1,60})"\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s*$'
)
# 无引号消息头（第三方/Mac 导出）：张三 2024-01-01 10:00:00（整行仅 名字+时间）
HEAD_PLAIN_RE = re.compile(
    r'^([^\s"\[\]【】][^"\n]{0,58}?)\s+'
    r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s*$'
)
# 日期分隔行：2024/3/1 周五 / 2024年3月1日 / 2024-03-01
DATE_LINE_RE = re.compile(
    r'^\s*(\d{4}\s*[年/-]\s*\d{1,2}\s*[月/-]\s*\d{1,2}\s*日?'
    r'(?:\s*(?:周|星期|礼拜)\s*[\d一二三四五六日天])?)\s*$'
)
# 标题行："项目群" 的聊天记录 / 项目群 的聊天记录 / 与"张三"的聊天记录
TITLE_RE = re.compile(r'^\s*["“]?(.+?)["”]?\s*的聊天记录\s*$')

# 群系统 / 非发言行（独立成行、无消息头）
SYSTEM_PATTERNS = [
    re.compile(p) for p in (
        r'^-{2,}.*-{2,}$',                       # --- 以上是打招呼的内容 ---
        r'邀请.+(加入|进了?).{0,4}群聊',
        r'撤回了一条消息',
        r'你已添加了|现在可以开始聊天',
        r'修改了群聊(名称|名字?)',
        r'(被|把).+(移出|踢出).{0,4}群',
        r'(成为|成为了).{0,6}群主|群主.{0,6}转让',
        r'^(群|本群|群聊)?公告',
        r'^\[系统(消息|提示)\]',
        r'开启了?朋友验证|发送朋友验证',
        r'以上是打招呼',
        r'消息记录（?此消息记录|^记录创建于',
        r'解散了该群|已退出群聊|加入了企业',
        r'成功上传了?群文件',
        r'^(对方)?正在(输入|通话)',
    )
]

# 多媒体/占位消息（真人发送，保留，复盘可知"发了文件/图"）
PLACEHOLDER_RE = re.compile(
    r'^\s*\[(图片|语音|视频|文件|位置|红包|转账|动画表情|表情|链接|聊天记录|'
    r'小程序|名片|语音通话|视频通话|位置共享|合并转发|拍了拍|引用|待办|日程)\]'
)


def _is_system_line(line: str) -> bool:
    if DATE_LINE_RE.match(line):
        return True
    for rx in SYSTEM_PATTERNS:
        if rx.search(line):
            return True
    return False


def parse_wechat_text(text: str, title: str | None = None) -> Conversation:
    messages: list[Message] = []
    cur: Message | None = None
    resolved_title = title

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = HEAD_QUOTED_RE.match(line) or HEAD_PLAIN_RE.match(line)
        if m:
            cur = Message(speaker=m.group(1).strip(), time=m.group(2).replace("/", "-"),
                          text="", kind="msg")
            messages.append(cur)
            continue
        if _is_system_line(line.strip()):
            # 日期分隔/系统提示：作为 system 消息，不并入上一条正文
            dm = DATE_LINE_RE.match(line.strip())
            messages.append(Message(
                speaker="系统", time=(dm.group(1).replace("年", "-").replace("月", "-")
                                      .replace("日", "").replace("/", "-") if dm else None),
                text=line.strip(), kind="system"))
            cur = None
            continue
        if resolved_title is None:
            tm = TITLE_RE.match(line)
            if tm:
                resolved_title = tm.group(1).strip()
                continue
        if cur is not None:
            cur.text = (cur.text + "\n" + line.strip()).strip()
        else:
            # 头部说明行（导出说明、统计等），归为系统信息但不影响
            if any(k in line for k in ("聊天记录", "记录创建于", "消息记录")):
                messages.append(Message(speaker="系统", time=None,
                                        text=line.strip(), kind="system"))

    # 剔除空正文（纯消息头无内容）与占位之外的空消息
    messages = [m for m in messages if m.text.strip()]
    user = [m for m in messages if m.kind != "system"]
    if not user:
        raise ValueError("未识别到微信消息格式")

    return Conversation(source="wechat",
                        title=resolved_title or "微信聊天记录",
                        messages=messages, raw_text=text)


def parse_wechat(path: str) -> Conversation:
    text, enc = read_text(path)
    conv = parse_wechat_text(text)
    conv.raw_text = text
    return conv
