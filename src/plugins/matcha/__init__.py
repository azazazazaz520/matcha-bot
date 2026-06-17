from __future__ import annotations

import logging

from nonebot import on_message, require
from nonebot.adapters import Event

require("nonebot_plugin_localstore")

from .config import matcha_config
from .handler import handle_message
from .provider import NLPProvider, OpenAIProvider
from .trigger import trigger_policy

logger = logging.getLogger(__name__)

__all__ = ["NLPProvider", "OpenAIProvider"]

_provider: NLPProvider | None = None


def get_provider() -> NLPProvider:
    """懒加载 provider：首次调用时根据配置新建实例。"""
    global _provider
    if _provider is None:
        _provider = _create_provider()
        logger.info("Provider 初始化成功: %s", _provider.name)
    return _provider


def _create_provider() -> NLPProvider:
    """根据配置创建 NLP provider 实例。"""
    name = matcha_config.matcha_nlp_provider
    if name == "openai":
        respond_model = matcha_config.matcha_nlp_respond_model or None
        return OpenAIProvider(
            api_key=matcha_config.matcha_nlp_api_key,
            base_url=matcha_config.matcha_nlp_base_url,
            model=matcha_config.matcha_nlp_model,
            respond_model=respond_model,
        )
    msg = f"Unknown NLP provider: {name}"
    raise ValueError(msg)


# 优先级设为最低，让命令类插件优先处理
chat = on_message(priority=99, block=False)


@chat.handle()
async def handle_chat(event: Event) -> None:
    text = event.get_plaintext().strip()
    if not text:
        return

    logger.info("收到消息: %s", text[:80])

    try:
        provider = get_provider()
    except Exception:
        logger.exception("Provider 初始化失败")
        await chat.finish("抹茶还没准备好…等会再来找我吧 (。-ω-)zzz")
        return

    reply = await handle_message(text, trigger_policy.get_session_key(event), provider)
    if reply:
        await chat.finish(reply)
    else:
        logger.info("决定不回复: %s", text[:80])
