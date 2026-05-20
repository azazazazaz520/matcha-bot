from pathlib import Path

# [核心配置] 运行模式选择
# "stable" : 仅打印决策结果和发送内容 + 真实发送 (生产环境)
# "log"    : 打印易读历史、思考链、决策、发送内容 + 真实发送 (观察环境)
# "test"   : 打印易读历史、思考链、决策、底层Prompt、底层Raw响应 + 拦截发送 (开发环境)
RUN_MODE = "log"

# [配置] 1. 唯一指定互动的群聊 (Bot会读取此群上下文并在此群回复)
REPLY_GROUP_ID = 940123987

# [配置] 2. 指定监听并记录日志的群聊列表
LISTEN_GROUP_IDS = []

# [配置] 3. 自我认知关键字 (出现这些词时，自动将target改为Me，并将词替换为"你")
SELF_KEYWORDS = ["友希", "Yuki", "yuki"]

DATA_DIR = Path("data")
USER_MAP_FILE_PATH = DATA_DIR / "user_map.json"

MAX_WINDOW_SIZE = 50
TIMEOUT_MINUTES = 240

# [配置] LLM 设置
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "Yuki_v1.2"

# --- 模式逻辑开关 ---
CAN_SEND_REAL_MSG = RUN_MODE in ["stable", "log"]
SHOW_PROCESS = RUN_MODE in ["log", "test"]
SHOW_RAW_DEBUG = RUN_MODE == "test"

if not DATA_DIR.exists():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
