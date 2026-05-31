import argparse
import os

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

from src.yuki import api


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动 友希 Bot")
    parser.add_argument(
        "--key1",
        default=os.getenv("YUKI_API_KEY", ""),
        help="回复模型的 API Key（可留空，此时从环境变量 YUKI_API_KEY 读取）",
    )
    parser.add_argument(
        "--key2",
        default=os.getenv("YUKI_DECISION_API_KEY", ""),
        help="决策模型的 API Key（可为空，为空时跳过决策、默认不回复）",
    )
    # 仅解析已知参数，避免与 nonebot 自身可能的参数冲突
    args, _ = parser.parse_known_args()
    return args


args = parse_args()

if not args.key1:
    raise SystemExit(
        "错误：未提供回复模型 API Key。请在 .env 中设置 YUKI_API_KEY 或通过 --key1 传入。"
    )

# 用命令行传入的 api-key 初始化模型客户端（命令行优先，env 兜底）
api.init_client(args.key1)
api.init_decision_client(args.key2)

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# 加载友希插件（须在 init 之后加载，因其导入时会用到 driver）
nonebot.load_plugin("src.yuki.bot")



if __name__ == "__main__":
    nonebot.run()
