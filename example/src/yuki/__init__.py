"""Yuki（友希）回复模块包。

- ``api``      —— 模型 API 调用层（回复模型 + 决策模型）。
- ``response`` —— 回复生成与回复控制（整合历史 / 决策 / tick）。
- ``bot``      —— NoneBot 插件层（监听目标群、定时触发、发送回复）。

注意：本 ``__init__`` 不导入 ``bot``，因为 ``bot`` 在导入时会调用
``get_driver()``，必须在 ``nonebot.init()`` 之后才能导入。``bot`` 由
``main.py`` 在 init 之后通过 ``nonebot.load_plugin("src.yuki.bot")`` 加载，
从而注册其中的消息监听器与启动钩子。
"""

from . import api, response

__all__ = ["api", "response"]


