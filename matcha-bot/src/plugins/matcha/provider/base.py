from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


type ChatMessage = dict[str, str]


class NLPProvider(ABC):
    """NLP provider 抽象基类，所有后端实现需继承此类。"""

    @abstractmethod
    async def should_respond(
        self, message: str, context: Sequence[ChatMessage]
    ) -> bool:
        """判断一条消息是否值得机器人回复（不被 @ 时的选回逻辑）。"""

    @abstractmethod
    async def generate_response(
        self, message: str, context: Sequence[ChatMessage]
    ) -> str:
        """基于消息和上下文生成回复文本。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """provider 名称，用于配置识别。"""
