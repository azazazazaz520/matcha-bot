from __future__ import annotations

import time
from typing import TYPE_CHECKING

from nonebot.adapters import Event

from .config import matcha_config

if TYPE_CHECKING:
    from .provider.base import NLPProvider

type SessionKey = str


class TriggerPolicy:
    """控制机器人何时回复消息。"""

    def __init__(self) -> None:
        self._last_response: dict[SessionKey, float] = {}
        self._global_timestamps: list[float] = []

    def is_command(self, text: str) -> bool:
        """过滤掉以 / 开头的命令消息。"""
        return text.lstrip().startswith("/")

    def is_must_respond(self, text: str) -> bool:
        """消息包含触发关键词时必回。"""
        return any(kw in text for kw in matcha_config.matcha_trigger_keywords)

    async def should_respond(
        self, session: SessionKey, text: str, provider: NLPProvider
    ) -> bool:
        """综合判断是否应该回复（包含频率控制）。"""
        # 命令消息不回复
        if self.is_command(text):
            return False

        # 必回条件：含关键词
        if self.is_must_respond(text):
            return self._check_cooldown(session)

        # 选回条件：provider 判断 + 冷却检查
        if not self._check_cooldown(session):
            return False
        if not self._check_global_rate():
            return False
        return await provider.should_respond(text, [])

    def record_response(self, session: SessionKey) -> None:
        now = time.time()
        self._last_response[session] = now
        self._global_timestamps.append(now)

    def _check_cooldown(self, session: SessionKey) -> bool:
        last = self._last_response.get(session, 0)
        return (time.time() - last) >= matcha_config.matcha_trigger_cooldown

    def _check_global_rate(self) -> bool:
        now = time.time()
        window = now - 60
        self._global_timestamps = [t for t in self._global_timestamps if t > window]
        return len(self._global_timestamps) < matcha_config.matcha_global_rate_limit

    def get_session_key(self, event: Event) -> SessionKey:
        """从事件中提取 session key。"""
        gid = getattr(event, "group_id", None)
        uid = getattr(event, "user_id", "unknown")
        return f"group_{gid}_user_{uid}" if gid else f"private_{uid}"


trigger_policy = TriggerPolicy()
