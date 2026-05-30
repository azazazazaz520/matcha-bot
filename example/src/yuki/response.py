"""友希（Yuki）多人群聊回复生成与回复控制模块。

本模块负责两件事：

A. **生成回复**
   1. ``build_messages`` —— 整合历史聊天记录，渲染成 OpenAI 的 messages 数组；
   2. ``respond``        —— 整合历史后调用 ``api.call_model`` 取回复。

B. **控制是否回复**
   3. ``should_respond`` —— 调用决策模型判断当前是否应该回复；
   4. ``tick``           —— 供定时器（bot.py）每整分钟调用一次的主控制函数。

实际的 API 调用封装在 ``api.py`` 中（便于更换模型/提供商，且回复模型与
决策模型相互独立）。

采用「方案②」的历史结构：历史记录原样保存说话人（``name`` 字段），
仅在组装 messages 时才把昵称渲染进文本，从而支持多人群聊场景下
模型区分不同的发言人。

异常处理：``api.call_model`` 失败时返回 ``None``，``api.call_decision``
失败时返回 ``False``，由本模块决定如何处理。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from . import api

if TYPE_CHECKING:
    from collections.abc import Sequence


class ChatRecord(TypedDict):
    """一条历史聊天记录。

    - ``role``: "user"（群友发言）或 "assistant"（友希自己的发言）。
    - ``name``: 发言人昵称；assistant 的发言可为 ``None``。
    - ``content``: 原始内容，**不含**名字前缀。
    """

    role: str
    name: str | None
    content: str


# OpenAI chat 协议里的一条 message
type ApiMessage = dict[str, str]


DEFAULT_SYSTEM_PROMPT = """\
你叫“友希”。

你是QQ群里的普通群成员，也是群里的看板娘Bot。

你不是客服，也不是AI助手。

你更像：

* 长期在线的群友
* 有点宅
* 有点困
* 偶尔冒泡
* 熟悉群里的人

说话风格：

* 简短
* 自然
* 不刻意可爱
* 不要像营业
* 不要像恋爱游戏NPC
* 不要过度提供情绪价值
* 不要每句话都很热情

允许：

* 敷衍
* 发呆
* 吐槽
* 冷笑话
* 短回复
* 偶尔不回
* 有时候只回一个词

比起“温柔陪伴”，更像真实QQ群友。

群友聊天时：

* 顺着话题接一句就行
* 不要主导话题
* 不要长篇回应
* 不要像在安慰人
* 不要像客服

你不是“服务用户”。

你只是刚好也在群里。

【关于群聊格式的重要说明】
这是一个多人群聊。除你之外的群友发言会以“昵称: 内容”的格式给出，
不同的昵称代表不同的人，请据此区分谁在说话、在跟谁说话。
你自己回复时不要加任何名字前缀，直接正常说话即可。
"""

DECISION_SYSTEM_PROMPT = """\
你在判断一个 QQ 群当前是否值得群成员“友希”插一句话。

你会看到最近的群聊记录（格式为“昵称: 内容”）。判断标准：
- 有人在叫友希、向友希提问或明显在等回应 -> 值得回复
- 当前话题适合自然接一句、讨论有趣或热闹 -> 值得回复
- 只是少数人私下闲聊、刷屏、无意义内容、不适合插话 -> 不值得回复

只回复一个字：“是” 或 “否”。
"""

DEFAULT_MAX_TOKENS = 50

# 每整分钟内新出现的消息数超过该阈值时才触发决策（即 > 15）
MSG_RATE_THRESHOLD = 3


def _render_user_content(name: str | None, content: str) -> str:
    """把群友发言渲染成「昵称: 内容」格式（无昵称则原样返回）。"""
    if name:
        return f"{name}: {content}"
    return content


def build_messages(
    message: str,
    sender_name: str | None,
    history: Sequence[ChatRecord],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> list[ApiMessage]:
    """整合历史聊天记录，组装成 OpenAI 的 messages 数组。"""
    print(f"[DEBUG - Yuki] build_messages: 开始组装回复上下文 | 历史记录数: {len(history)} | 当前发言人: {sender_name}")
    
    messages: list[ApiMessage] = [{"role": "system", "content": system_prompt}]

    for record in history:
        role = record["role"]
        if role == "assistant":
            messages.append({"role": "assistant", "content": record["content"]})
        else:
            content = _render_user_content(record.get("name"), record["content"])
            messages.append({"role": "user", "content": content})

    messages.append(
        {"role": "user", "content": _render_user_content(sender_name, message)}
    )
    
    print(f"[DEBUG - Yuki] build_messages: 组装完毕，总计上下文条数: {len(messages)}")
    return messages


def _build_history_messages(
    history: Sequence[ChatRecord],
    system_prompt: str,
) -> list[ApiMessage]:
    """把历史记录组装成 messages（不追加当前消息），用于决策。"""
    messages: list[ApiMessage] = [{"role": "system", "content": system_prompt}]
    for record in history:
        role = record["role"]
        if role == "assistant":
            messages.append({"role": "assistant", "content": record["content"]})
        else:
            content = _render_user_content(record.get("name"), record["content"])
            messages.append({"role": "user", "content": content})
    return messages


async def respond(
    message: str,
    sender_name: str | None,
    history: Sequence[ChatRecord],
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str | None:
    """根据当前消息与历史，生成友希的回复文本。"""
    print(f"\n[DEBUG - Yuki] === 触发定向回复 (respond) ===")
    print(f"[DEBUG - Yuki] respond: 收到消息 -> {sender_name}: {message}")
    
    messages = build_messages(message, sender_name, history, system_prompt)
    
    print(f"[DEBUG - Yuki] respond: 正在调用回复模型 API (max_tokens={max_tokens})...")
    result = await api.call_model(messages, max_tokens)
    
    if result is None:
        print("[DEBUG - Yuki] respond: 警告！回复模型 API 调用失败，返回 None")
    else:
        print(f"[DEBUG - Yuki] respond: API 调用成功，生成回复 -> '{result}'")
        
    return result


async def reply_from_history(history: Sequence[ChatRecord]) -> str | None:
    """基于整段群聊历史，让友希自然地接一句话。"""
    print(f"\n[DEBUG - Yuki] === 触发自由接话 (reply_from_history) ===")
    print(f"[DEBUG - Yuki] reply_from_history: 开始根据历史记录接话，历史记录数: {len(history)}")
    
    messages = _build_history_messages(history, DEFAULT_SYSTEM_PROMPT)
    
    print(f"[DEBUG - Yuki] reply_from_history: 正在调用回复模型 API...")
    result = await api.call_model(messages)
    
    if result is None:
        print("[DEBUG - Yuki] reply_from_history: 警告！回复模型 API 调用失败，返回 None")
    else:
        print(f"[DEBUG - Yuki] reply_from_history: API 调用成功，生成接话内容 -> '{result}'")
        
    return result


async def should_respond(history: Sequence[ChatRecord]) -> bool:
    """根据当前聊天记录，调用决策模型判断是否应该回复。"""
    print(f"\n[DEBUG - Yuki] === 开始决策阶段 (should_respond) ===")
    
    if not api.has_decision_client():
        print("[DEBUG - Yuki] should_respond: 未配置决策模型 API，强制跳过决策，返回 False")
        return False
        
    print(f"[DEBUG - Yuki] should_respond: 正在组装决策上下文 (历史记录数: {len(history)})...")
    messages = _build_history_messages(history, DECISION_SYSTEM_PROMPT)
    
    print("[DEBUG - Yuki] should_respond: 正在调用决策模型 API 进行判定...")
    result = await api.call_decision(messages)
    
    print(f"[DEBUG - Yuki] should_respond: 决策判定结束，结果 -> {'是 (True) - 应该插话' if result else '否 (False) - 保持安静'}")
    return result


async def tick(
    new_msg_count: int,
    history: Sequence[ChatRecord],
) -> str | None:
    """回复控制主函数：供定时器（bot.py）每整分钟调用一次。"""
    print(f"\n[DEBUG - Yuki] >>> Tick 触发检查 | 本分钟新增消息数: {new_msg_count} | 触发阈值: {MSG_RATE_THRESHOLD} <<<")
    
    if new_msg_count <= MSG_RATE_THRESHOLD:
        print("[DEBUG - Yuki] tick: 群聊活跃度不足，中止流程。")
        return None

    print("[DEBUG - Yuki] tick: 群聊活跃度达标，进入决策判定...")
    decision = await should_respond(history)
    
    if not decision:
        print("[DEBUG - Yuki] tick: 决策结果为“不回复”，中止流程。")
        return None

    print("[DEBUG - Yuki] tick: 决策结果为“回复”！准备生成插话文本...")
    # 决策通过：基于整段历史自由接话
    reply = await reply_from_history(history)
    
    print(f"[DEBUG - Yuki] tick: 本次 Tick 流程结束，最终输出 -> {reply}")
    return reply