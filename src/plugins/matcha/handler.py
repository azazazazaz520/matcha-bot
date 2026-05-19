from __future__ import annotations

from typing import TYPE_CHECKING

from .config import matcha_config
from .context import ContextManager
from .trigger import trigger_policy

if TYPE_CHECKING:
    from .provider.base import NLPProvider

context_manager = ContextManager(max_rounds=matcha_config.matcha_context_max_rounds)


async def handle_message(
    text: str,
    session: str,
    provider: NLPProvider,
) -> str | None:
    """核心处理入口。返回回复文本，或 None 表示不回复。"""
    if not await trigger_policy.should_respond(session, text, provider):
        return None

    ctx = context_manager.get_context(session)
    context_manager.add_message(session, "user", text)

    reply = await provider.generate_response(text, ctx)
    context_manager.add_message(session, "assistant", reply)
    trigger_policy.record_response(session)

    return reply
