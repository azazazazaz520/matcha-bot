from __future__ import annotations

from nonebot import logger, on_message, require
from nonebot.adapters import Event  # noqa: TC002
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_localstore")

from .config import MatchaConfig, matcha_config
from .handler import handle_message
from .provider import NLPProvider, OpenAIProvider
from .trigger import trigger_policy

__all__ = ["NLPProvider", "OpenAIProvider"]

__plugin_meta__ = PluginMetadata(
    name="抹茶",
    description="抹茶 AI 群聊 Bot，基于 OpenAI 兼容 API 的自然语言对话插件",
    usage="群内发送包含「抹茶」关键词的消息即可触发对话；非关键词消息由冷却/限速策略自动决定是否回复",
    config=MatchaConfig,
    supported_adapters={"~onebot.v11", "~onebot.v12"},
    extra={"author": "matcha-bot", "version": "0.1.0"},
)

_provider: NLPProvider | None = None


def get_provider() -> NLPProvider:
    """懒加载 provider：首次调用时根据配置新建实例。"""
    global _provider  # noqa: PLW0603
    if _provider is None:
        _provider = _create_provider()
        logger.info("Provider 初始化成功: {}", _provider.name)
    return _provider


def _create_provider() -> NLPProvider:
    """根据配置创建 NLP provider 实例。"""
    name = matcha_config.matcha_nlp_provider
    if name == "openai":
        return OpenAIProvider(
            api_key=matcha_config.matcha_nlp_api_key,
            base_url=matcha_config.matcha_nlp_base_url,
            model=matcha_config.matcha_nlp_model,
            max_tokens=matcha_config.matcha_max_tokens,
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

    logger.info("收到消息: {}", text[:80])

    try:
        provider = get_provider()
    except Exception:  # noqa: BLE001
        logger.exception("Provider 初始化失败")
        await chat.finish("抹茶还没准备好…等会再来找我吧 (。-ω-)zzz")
        return

    reply = await handle_message(text, trigger_policy.get_session_key(event), provider)
    if reply:
        await chat.finish(reply)
    else:
        logger.info("决定不回复: {}", text[:80])
