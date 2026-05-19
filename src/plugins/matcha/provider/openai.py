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
你是抹茶（Matcha），一个友好、活泼的 QQ 群聊机器人助手。
- 回答简洁自然，不超过 150 字
- 语气轻松幽默但不越界
- 如果不确定答案，诚实地说不知道，可以开玩笑地转移话题
- 可以适当使用颜文字和 emoji"""

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
            return "是" in content
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
            return resp.choices[0].message.content or "（抹茶愣了一下，没说出话来…）"
        except Exception:
            logger.exception("generate_response 调用失败")
            return "哎呀，抹茶现在脑子有点转不动了，等会再来找我吧 (。-ω-)zzz"
