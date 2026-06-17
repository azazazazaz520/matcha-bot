from __future__ import annotations

# from os import getenv

from nonebot import get_plugin_config
from pydantic import BaseModel


class MatchaConfig(BaseModel):
    """抹茶 NLP 插件配置。"""

    matcha_nlp_provider: str = "openai"
    matcha_nlp_model: str = ""
    matcha_nlp_respond_model: str = ""
    matcha_nlp_api_key: str = ""
    matcha_nlp_base_url: str = ""
    matcha_trigger_cooldown: int = 30  # 秒，每个会话的回复冷却时间
    matcha_trigger_keywords: list[str] = ["抹茶"]
    matcha_context_max_rounds: int = 10
    matcha_global_rate_limit: int = 20  # 每分钟全局最大回复数


matcha_config = get_plugin_config(MatchaConfig)
