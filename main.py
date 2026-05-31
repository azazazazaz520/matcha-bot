import argparse

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

from src.yuki import api


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动 友希 Bot")
    parser.add_argument(
        "--key1",
        required=True,
        help="回复模型的 API Key（启动时动态注入）",
    )
    parser.add_argument(
        "--key2",
        default="",
        help="决策模型的 API Key（可为空，为空时跳过决策、默认不回复）",
    )
    # 仅解析已知参数，避免与 nonebot 自身可能的参数冲突
    args, _ = parser.parse_known_args()
    return args


args = parse_args()

# 用命令行传入的 api-key 初始化模型客户端
api.init_client(args.key1)
api.init_decision_client(args.key2)

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# 加载友希插件（须在 init 之后加载，因其导入时会用到 driver）
nonebot.load_plugin("src.yuki.bot")



if __name__ == "__main__":
    nonebot.run()
