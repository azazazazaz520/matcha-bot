from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nonebot_plugin_localstore import get_plugin_data_dir

from .config import matcha_config
from .context import ContextManager
from .trigger import trigger_policy

if TYPE_CHECKING:
    from .provider.base import NLPProvider

logger = logging.getLogger(__name__)

# 持久化目录由 nonebot_plugin_localstore 提供，自动创建
# 默认路径：%LOCALAPPDATA%/nonebot2/matcha/contexts/
# 若在 .env 中设置 LOCALSTORE_USE_CWD=true，则改为 ./data/matcha/contexts/
_context_data_dir = get_plugin_data_dir() / "contexts"

context_manager = ContextManager(
    max_rounds=matcha_config.matcha_context_max_rounds,
    data_dir=_context_data_dir,
)
logger.info("上下文持久化目录: %s", _context_data_dir)


async def handle_message(
    text: str,
    session: str,
    provider: NLPProvider,
) -> str | None:
    """核心处理入口。返回回复文本，或 None 表示不回复。"""
    should = await trigger_policy.should_respond(session, text, provider)
    logger.info("触发判定: %s → %s", text[:50], "回复" if should else "忽略")
    if not should:
        return None

    ctx = context_manager.get_context(session)
    context_manager.add_message(session, "user", text)

    reply = await provider.generate_response(text, ctx)
    context_manager.add_message(session, "assistant", reply)
    trigger_policy.record_response(session)

    return reply
