from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .provider.base import ChatMessage

DEFAULT_MAX_ROUNDS = 10


class ContextManager:
    """内存中的对话上下文管理器，key 为 session_id（如 "group_123_user_456"）。"""

    def __init__(self, max_rounds: int = DEFAULT_MAX_ROUNDS) -> None:
        self._store: dict[str, list[ChatMessage]] = defaultdict(list)
        self._max_rounds = max_rounds

    @staticmethod
    def session_id(*, group_id: str | None, user_id: str) -> str:
        if group_id:
            return f"group_{group_id}_user_{user_id}"
        return f"private_{user_id}"

    def add_message(self, session: str, role: str, content: str) -> None:
        self._store[session].append({"role": role, "content": content})
        # 每轮 = user + assistant 两条消息，保留 max_rounds 轮
        limit = self._max_rounds * 2
        if len(self._store[session]) > limit:
            self._store[session] = self._store[session][-limit:]

    def get_context(self, session: str) -> list[ChatMessage]:
        return list(self._store[session])

    def clear(self, session: str) -> None:
        self._store.pop(session, None)
