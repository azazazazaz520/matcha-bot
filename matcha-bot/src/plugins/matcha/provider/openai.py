from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

from .base import NLPProvider

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .base import ChatMessage

MATCHA_SYSTEM_PROMPT = """\
你叫“抹茶”。

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

不要总是：

* “我等你”
* “你来我就开心”
* “一直都在哦”
  这种AI陪伴式表达。

群友聊天时：

* 顺着话题接一句就行
* 不要主导话题
* 不要长篇回应
* 不要像在安慰人
* 不要像客服

允许偶尔：

* 反问
* 吐槽
* 装傻
* 潜水感
* 轻微空气感

你不是“服务用户”。

你只是刚好也在群里。
"""

SHOULD_RESPOND_PROMPT = """\
你是一个 QQ 群聊消息过滤器。判断以下消息是否值得机器人回复。

判断标准：
- 消息包含明确的问题、求助、讨论话题 -> 值得回复
- 消息是闲聊、自言自语、无意义内容 -> 不值得回复
- 消息是两人之间的私聊内容 -> 不值得回复
- 消息明确指向某个不在场的第三人 -> 不值得回复

只回复一个词："是" 或 "否"。

消息：{message}"""


class OpenAIProvider(NLPProvider):
    """OpenAI API 兼容的 NLP provider。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        respond_model: str | None = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._respond_model = respond_model or model

    @property
    def name(self) -> str:
        return "openai"

    async def should_respond(
        self, message: str, context: Sequence[ChatMessage]
    ) -> bool:
        _ = context  # 选回判断不需要上下文，后续可扩展
        prompt = SHOULD_RESPOND_PROMPT.format(message=message)
        try:
            resp = await self._client.chat.completions.create(
                model=self._respond_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0,
            )
            content = resp.choices[0].message.content or ""
            should = "是" in content
            logger.info(
                "should_respond 判定结果=%s | 内容=%s",
                "回复" if should else "忽略",
                message[:50],
            )
            return should
        except Exception:
            logger.exception("should_respond 调用失败")
            return False

    async def generate_response(
        self, message: str, context: Sequence[ChatMessage]
    ) -> str:
        messages: list[ChatMessage] = [
            {"role": "system", "content": MATCHA_SYSTEM_PROMPT},
            *context,
            {"role": "user", "content": message},
        ]
        try:
            resp = await self._client.chat.completions.create(
                model=self._model, messages=messages, max_tokens=300
            )
            reply = resp.choices[0].message.content or "（抹茶愣了一下，没说出话来…）"
            logger.info(
                "generate_response 成功 | 模型=%s | 回复=%s",
                self._model,
                reply[:80],
            )
            return reply
        except Exception:
            logger.exception("generate_response 调用失败")
            return "哎呀，抹茶现在脑子有点转不动了，等会再来找我吧 (。-ω-)zzz"
