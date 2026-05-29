from __future__ import annotations

from nonebot import on_message, require
from nonebot.adapters import Event

require("nonebot_plugin_localstore")

from .config import matcha_config
from .handler import handle_message
from .provider import NLPProvider, OpenAIProvider
from .trigger import trigger_policy

__all__ = ["NLPProvider", "OpenAIProvider"]


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


_provider = _create_provider()

# 优先级设为最低，让命令类插件优先处理
chat = on_message(priority=99, block=False)


@chat.handle()
async def handle_chat(event: Event) -> None:
    text = event.get_plaintext().strip()
    if not text:
        return

    session = trigger_policy.get_session_key(event)
    reply = await handle_message(text, session, _provider)
    if reply:
        await chat.finish(reply)
