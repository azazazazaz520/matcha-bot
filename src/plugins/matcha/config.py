from __future__ import annotations

from nonebot import get_plugin_config
from pydantic import BaseModel, Field


class MatchaConfig(BaseModel):
    """抹茶 NLP 插件配置。"""

    matcha_nlp_provider: str = "openai"
    matcha_nlp_model: str = "gpt-4o-mini"
    matcha_nlp_api_key: str = ""
    matcha_nlp_base_url: str = "https://api.openai.com/v1"
    matcha_trigger_cooldown: int = Field(
        default=30, gt=0, description="每个会话的回复冷却时间（秒）"
    )
    matcha_trigger_keywords: list[str] = Field(
        default=["抹茶"], description="触发关键词列表"
    )
    matcha_context_max_rounds: int = Field(
        default=10, ge=1, description="最大保留对话轮数"
    )
    matcha_global_rate_limit: int = Field(
        default=20, gt=0, description="每分钟全局最大回复数"
    )
    matcha_max_tokens: int = Field(
        default=300, ge=1, description="生成回复的最大 token 数"
    )


matcha_config = get_plugin_config(MatchaConfig)
