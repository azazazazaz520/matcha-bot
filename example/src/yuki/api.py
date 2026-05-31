"""模型 API 调用层。

把「创建客户端」与「调用模型」收拢在此模块，便于后续更换模型或 API
提供商。配置（BASE_URL / MODEL）在此硬编码，api_key 由父级目录的
``main.py`` 在启动时动态注入。

本模块同时管理两套模型：

- **回复模型**：用于生成友希的回复（``call_model``）。
- **决策模型**：用于判断当前是否应该回复（``call_decision``），其 api_key
  可为空，为空时不创建客户端、由上层跳过决策。

异常处理策略：调用发生异常时只在控制台打印信息，并返回特殊返回值
（``call_model`` 返回 ``None``，``call_decision`` 返回 ``False``）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---- 回复模型配置（硬编码，可更换）----
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-pro"
DEFAULT_MAX_TOKENS = 300

# ---- 决策模型配置（硬编码，可与回复模型不同）----
DECISION_BASE_URL = "https://api.deepseek.com"
DECISION_MODEL = "deepseek-v4-pro"

# OpenAI chat 协议里的一条 message
type ApiMessage = dict[str, str]

# 模块级客户端，由 main.py 启动时注入
_client: AsyncOpenAI | None = None
_decision_client: AsyncOpenAI | None = None


# --------------------------------------------------------------------------- #
# 回复模型
# --------------------------------------------------------------------------- #
def init_client(api_key: str) -> AsyncOpenAI:
    """用传入的 api_key 初始化回复模型客户端，并返回该客户端。"""
    global _client
    _client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


def get_client() -> AsyncOpenAI:
    """获取已初始化的回复模型客户端，未初始化时抛错。"""
    if _client is None:
        msg = "回复模型 client 尚未初始化，请先调用 init_client(api_key)。"
        raise RuntimeError(msg)
    return _client


async def call_model(
    messages: Sequence[ApiMessage],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str | None:
    """调用回复模型，成功返回回复文本，异常时打印并返回 ``None``。"""
    try:
        client = get_client()
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=cast("list[Any]", list(messages)),
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        print(f"[yuki.api] 调用回复模型失败: {e}")
        return None


# --------------------------------------------------------------------------- #
# 决策模型
# --------------------------------------------------------------------------- #
def init_decision_client(api_key: str | None) -> AsyncOpenAI | None:
    """用传入的 api_key 初始化决策模型客户端。

    api_key 为空（None / 空串）时不创建客户端，返回 ``None``，
    上层据此跳过决策阶段。
    """
    global _decision_client
    if not api_key:
        _decision_client = None
        return None
    _decision_client = AsyncOpenAI(api_key=api_key, base_url=DECISION_BASE_URL)
    return _decision_client


def has_decision_client() -> bool:
    """决策模型客户端是否已就绪。"""
    return _decision_client is not None


async def call_decision(messages: Sequence[ApiMessage]) -> bool:
    """调用决策模型判断是否应该回复。

    让模型只回「是/否」，含「是」即返回 ``True``。
    未初始化决策客户端或发生异常时打印并返回 ``False``（默认不回复）。
    """
    if _decision_client is None:
        return False
    try:
        resp = await _decision_client.chat.completions.create(
            model=DECISION_MODEL,
            messages=cast("list[Any]", list(messages)),
            max_tokens=100,
            temperature=0,
        )
        content = resp.choices[0].message.content or ""
        print(f"[yuki.api] 决策模型原始输出: {content!r}")
        return "是" in content
    except Exception as e:  # noqa: BLE001
        print(f"[yuki.api] 调用决策模型失败: {e}")
        return False
