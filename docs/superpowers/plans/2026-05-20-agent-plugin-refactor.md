# Agent Plugin Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic `agent/src/plugins/agent.py` (394 lines) into a Python package `agent/src/plugins/agent/` with 6 modules, each responsible for a single concern. External behavior is preserved.

**Architecture:** Bottom-up extraction — config first (no deps), then data modules (user_map, chat_window), then logic modules (llm, handlers), finally the entry-point `__init__.py` that assembles everything. Dependencies are acyclic: `__init__` → handlers → llm → chat_window → user_map → config.

**Tech Stack:** Python 3.x, NoneBot, httpx, standard library

---

### Task 1: Create package directory and extract `config.py`

**Files:**
- Create: `agent/src/plugins/agent/__init__.py` (empty placeholder)
- Create: `agent/src/plugins/agent/config.py`
- Modify: `agent/src/plugins/agent.py` (remove config section, add package import)

- [ ] **Step 1: Create the package directory**

```bash
mkdir -p agent/src/plugins/agent
```

- [ ] **Step 2: Write `config.py` with all configuration constants**

```python
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
```

- [ ] **Step 3: Verify config.py imports cleanly**

```bash
cd agent && python -c "from src.plugins.agent.config import RUN_MODE, REPLY_GROUP_ID; print('config OK:', RUN_MODE, REPLY_GROUP_ID)"
```

- [ ] **Step 4: Commit**

```bash
git add agent/src/plugins/agent/
git commit -m "refactor: extract config.py from monolithic agent plugin"
```

---

### Task 2: Extract `user_map.py`

**Files:**
- Create: `agent/src/plugins/agent/user_map.py`

- [ ] **Step 1: Write `user_map.py` with user mapping logic**

```python
import json
from typing import Union, Optional

from .config import USER_MAP_FILE_PATH

user_map = {}


def load_user_map():
    if USER_MAP_FILE_PATH.exists():
        try:
            with open(USER_MAP_FILE_PATH, "r", encoding="utf-8") as f:
                content = json.loads(f.read().strip() or "{}")
                user_map.clear()
                user_map.update(content)
        except Exception:
            user_map.clear()


def save_user_map():
    try:
        with open(USER_MAP_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(user_map, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


load_user_map()


def get_anonymous_id(real_qq_id: Union[str, int], bot_self_id: Union[str, int]) -> str:
    real_qq_id, bot_self_id = str(real_qq_id), str(bot_self_id)
    if real_qq_id == bot_self_id:
        if user_map.get(real_qq_id) != "Me":
            user_map[real_qq_id] = "Me"
            save_user_map()
        return "Me"
    if real_qq_id in user_map:
        return user_map[real_qq_id]
    existing_indexes = [
        int(uid[4:])
        for uid in user_map.values()
        if uid.startswith("User") and uid[4:].isdigit()
    ]
    new_id = f"User{max(existing_indexes) + 1 if existing_indexes else 1}"
    user_map[real_qq_id] = new_id
    save_user_map()
    return new_id


def get_real_id_by_anon(anon_id: str) -> Optional[str]:
    for real_qq, u_id in user_map.items():
        if u_id == anon_id:
            return real_qq
    return None
```

Change from original: replaced `global user_map` assignment in `load_user_map()` with `.clear()` + `.update()` so the module-level reference stays intact for other functions that use `user_map`.

- [ ] **Step 2: Verify user_map imports cleanly**

```bash
cd agent && python -c "from src.plugins.agent.user_map import get_anonymous_id; print('user_map OK:', get_anonymous_id('123', '456'))"
```

- [ ] **Step 3: Commit**

```bash
git add agent/src/plugins/agent/user_map.py
git commit -m "refactor: extract user_map.py from monolithic agent plugin"
```

---

### Task 3: Extract `chat_window.py`

**Files:**
- Create: `agent/src/plugins/agent/chat_window.py`

- [ ] **Step 1: Write `chat_window.py` with ChatWindowManager and singleton instance**

```python
from datetime import datetime
from typing import List, Dict, Union, Optional

from .config import MAX_WINDOW_SIZE, TIMEOUT_MINUTES


class ChatWindowManager:
    def __init__(self):
        self.window: List[Dict] = []

    def _should_clear(self, new_time: datetime) -> bool:
        if not self.window:
            return False
        last_time = self.window[-1]["_raw_time"]
        if (new_time - last_time).total_seconds() > (TIMEOUT_MINUTES * 60):
            return True
        if new_time.date() != last_time.date():
            return True
        return False

    def add_message(
        self,
        user: str,
        message: str,
        target: str = "none",
        group_id: Union[str, int] = 0,
    ):
        current_dt = datetime.now()
        if self._should_clear(current_dt):
            self.window.clear()

        record = {
            "time": current_dt.strftime("%H:%M:%S"),
            "user": user,
            "message": message,
            "target": target,
            "group_id": str(group_id),
            "_raw_time": current_dt,
        }
        self.window.append(record)
        if len(self.window) > MAX_WINDOW_SIZE:
            self.window.pop(0)

    @staticmethod
    def _escape_xml(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def build_prompt_content(self) -> str:
        if not self.window:
            return ""
        xml_lines = ["<history>"]
        for r in self.window:
            safe_msg = self._escape_xml(str(r["message"]))
            line = f'  <msg time="{r["time"]}" user="{r["user"]}" target="{r["target"]}">{safe_msg}</msg>'
            xml_lines.append(line)
        xml_lines.append("</history>")
        current_time_str = datetime.now().strftime("%H:%M:%S")
        xml_lines.append(f"<current_time>{current_time_str}</current_time>")
        return "\n".join(xml_lines)

    def get_readable_history(self) -> str:
        lines = []
        for r in self.window:
            tgt = f" -> {r['target']}" if r["target"] != "none" else ""
            lines.append(f"[{r['time']}] {r['user']}{tgt}: {r['message']}")
        return "\n".join(lines)

    def get_latest_msg_time(self) -> Optional[datetime]:
        if not self.window:
            return None
        return self.window[-1]["_raw_time"]


chat_window = ChatWindowManager()
```

Change: extracted `_escape_xml` as a static method.

- [ ] **Step 2: Verify chat_window imports cleanly**

```bash
cd agent && python -c "from src.plugins.agent.chat_window import chat_window; chat_window.add_message('test', 'hello'); print('chat_window OK:', chat_window.get_readable_history())"
```

- [ ] **Step 3: Commit**

```bash
git add agent/src/plugins/agent/chat_window.py
git commit -m "refactor: extract chat_window.py from monolithic agent plugin"
```

---

### Task 4: Extract `llm.py`

**Files:**
- Create: `agent/src/plugins/agent/llm.py`

- [ ] **Step 1: Write `llm.py` with Ollama query and response handling**

```python
import re
import asyncio
import httpx
from typing import Optional

from nonebot import get_bot
from nonebot.adapters import Message, MessageSegment
from nonebot.exception import ActionFailed

from .config import (
    OLLAMA_API_URL,
    OLLAMA_MODEL,
    RUN_MODE,
    SHOW_PROCESS,
    SHOW_RAW_DEBUG,
    CAN_SEND_REAL_MSG,
    REPLY_GROUP_ID,
)
from .user_map import get_real_id_by_anon


async def query_ollama(content_text: str) -> Optional[str]:
    messages = [
        {"role": "system", "content": "Chat"},
        {"role": "user", "content": content_text},
    ]
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "5m",
        "options": {"temperature": 0.7, "num_ctx": 4096},
    }
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(OLLAMA_API_URL, json=payload)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")
    except Exception as e:
        print(f"[Error] Ollama API Error: {e}")
        return None


async def handle_model_response(raw_text: str) -> str:
    if not raw_text:
        return "WAIT"

    think_match = re.search(r"<think>(.*?)</think>", raw_text, re.DOTALL)
    think_content = think_match.group(1).strip() if think_match else ""

    choice_match = re.search(r"<choice>(.*?)</choice>", raw_text)
    choice = choice_match.group(1).strip() if choice_match else "WAIT"

    replies = re.findall(
        r'<reply target="(.*?)">(.*?)</reply>', raw_text, re.DOTALL
    )

    print_prefix = f"[LLM | {RUN_MODE.upper()}]"

    if SHOW_PROCESS and think_content:
        print(f"\n{print_prefix} Think:\n{think_content}\n")

    if choice != "WAIT" or SHOW_PROCESS:
        print(f"{print_prefix} Decision: {choice}")

    if choice == "SEND" and replies:
        if CAN_SEND_REAL_MSG:
            try:
                bot = get_bot()
            except ValueError:
                print("[Error] 未连接到 OneBot，无法发送")
                return "WAIT"

        for target_user, text_content in replies:
            text_content = text_content.strip()
            if not text_content:
                continue

            msg_chain = Message(text_content)
            if target_user and target_user.lower() != "none":
                real_qq = get_real_id_by_anon(target_user)
                if real_qq:
                    msg_chain = (
                        MessageSegment.at(real_qq) + " " + msg_chain
                    )

            log_target_str = (
                f"@{target_user}"
                if (target_user and target_user.lower() != "none")
                else "All"
            )

            if CAN_SEND_REAL_MSG:
                print(
                    f"[Action] 发送给群 {REPLY_GROUP_ID} | {log_target_str}: {text_content}"
                )
                try:
                    await bot.send_group_msg(
                        group_id=REPLY_GROUP_ID, message=msg_chain
                    )
                except ActionFailed as e:
                    print(f"[Error] 发送失败: {e}")
            else:
                print(
                    f"[Mock] 假装发送 -> 群: {REPLY_GROUP_ID} | {log_target_str}: {text_content}"
                )

            await asyncio.sleep(1.0)
        return "SEND"
    return "WAIT"
```

- [ ] **Step 2: Verify llm.py imports cleanly (will fail without a running bot, but import should succeed)**

```bash
cd agent && python -c "from src.plugins.agent.llm import query_ollama, handle_model_response; print('llm.py import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agent/src/plugins/agent/llm.py
git commit -m "refactor: extract llm.py from monolithic agent plugin"
```

---

### Task 5: Extract `handlers.py`

**Files:**
- Create: `agent/src/plugins/agent/handlers.py`

- [ ] **Step 1: Write `handlers.py` with all event handlers and the self-mention resolver**

```python
import json
import re
from datetime import datetime
from typing import Tuple

from nonebot import on_message, on_command
from nonebot.adapters import Bot, GroupMessageEvent
from nonebot.exception import ActionFailed

from .config import REPLY_GROUP_ID, LISTEN_GROUP_IDS, SELF_KEYWORDS, DATA_DIR, RUN_MODE, SHOW_PROCESS, SHOW_RAW_DEBUG
from .llm import query_ollama, handle_model_response
from .chat_window import chat_window
from .user_map import get_anonymous_id


def resolve_self_mention(msg: str, target: str) -> Tuple[str, str]:
    triggered = False
    for kw in SELF_KEYWORDS:
        if kw in msg:
            msg = msg.replace(kw, "你")
            triggered = True

    if triggered:
        target = "Me"

    return msg, target


def _persist_message(
    sender_id: str, message: str, target_id: str, group_id: int, current_dt: datetime
):
    record_data = {
        "time": current_dt.strftime("%H:%M:%S"),
        "user": sender_id,
        "message": message,
        "target": target_id,
        "group_id": group_id,
    }
    group_dir = DATA_DIR / str(group_id)
    if not group_dir.exists():
        group_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(
            group_dir / f"{current_dt.strftime('%Y-%m-%d')}.jsonl", "a", encoding="utf-8"
        ) as f:
            f.write(json.dumps(record_data, ensure_ascii=False) + "\n")
    except Exception:
        pass


# --- 消息监听 ---
recorder = on_message(priority=1, block=False)


@recorder.handle()
async def record_message(bot: Bot, event: GroupMessageEvent):
    current_group_id = event.group_id

    msg, target, target_id = "", "none", "none"
    if event.reply:
        target = get_anonymous_id(event.reply.sender.user_id, bot.self_id)
        target_id = str(event.reply.sender.user_id)
    for seg in event.message:
        if seg.type == "text":
            msg += seg.data["text"]
        elif seg.type == "at":
            target = get_anonymous_id(seg.data["qq"], bot.self_id)
            target_id = str(seg.data["qq"])
    msg = msg.strip()

    if not msg:
        return

    # 持久化日志 (原始消息，不替换关键词)
    if current_group_id in LISTEN_GROUP_IDS:
        sender_id = str(event.user_id)
        current_dt = datetime.now()
        _persist_message(sender_id, msg, target_id, current_group_id, current_dt)

    # LLM 上下文 (预处理后)
    if current_group_id == REPLY_GROUP_ID:
        processed_msg, processed_target = resolve_self_mention(msg, target)
        chat_window.add_message(
            get_anonymous_id(event.user_id, bot.self_id),
            processed_msg,
            processed_target,
            group_id=current_group_id,
        )


# --- Bot Hook ---
@Bot.on_calling_api
async def capture_bot_send(bot: Bot, api: str, data: dict):
    if api != "send_group_msg" or data.get("group_id") != REPLY_GROUP_ID:
        return

    raw = data.get("message")
    msg, target = "", "none"
    if isinstance(raw, str):
        if m := re.search(r"\[CQ:at,qq=(\d+)\]", raw):
            target = get_anonymous_id(m.group(1), bot.self_id)
        msg = re.sub(r"\[CQ:.*?\]", "", raw)
    elif isinstance(raw, list) or hasattr(raw, "__iter__"):
        for s in raw:
            d = s.data if hasattr(s, "data") else s.get("data")
            t = s.type if hasattr(s, "type") else s.get("type")
            if t == "text":
                msg += d.get("text", "")
            elif t == "at":
                target = get_anonymous_id(d.get("qq"), bot.self_id)

    msg = msg.strip()
    if msg:
        chat_window.add_message(
            get_anonymous_id(bot.self_id, bot.self_id),
            msg,
            target,
            group_id=data.get("group_id"),
        )


# --- 调试命令 ---
debug_trigger = on_command("force_beat", priority=5)


@debug_trigger.handle()
async def force_beat(bot: Bot, event: GroupMessageEvent):
    if event.group_id != REPLY_GROUP_ID:
        return

    await debug_trigger.send(f"强制心跳... (Mode: {RUN_MODE})")
    prompt = chat_window.build_prompt_content()

    if SHOW_RAW_DEBUG:
        print(f"\n[Debug] Force Prompt:\n{prompt}")
    elif SHOW_PROCESS:
        print(f"\n[History] Force Context:\n{chat_window.get_readable_history()}")

    resp = await query_ollama(prompt)

    if SHOW_RAW_DEBUG:
        print(f"\n[Debug] Force Response:\n{resp}")

    await handle_model_response(resp)
```

Changes:
- `_` → `record_message`, `handle_bot_send` → `capture_bot_send`, `_` → `force_beat`
- Persistence logic extracted to `_persist_message()`

- [ ] **Step 2: Verify handlers.py imports without errors (NoneBot handlers are registered at import)**

```bash
cd agent && python -c "from src.plugins.agent.handlers import recorder, debug_trigger; print('handlers.py import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agent/src/plugins/agent/handlers.py
git commit -m "refactor: extract handlers.py from monolithic agent plugin"
```

---

### Task 6: Create `__init__.py` and wire everything together

**Files:**
- Overwrite: `agent/src/plugins/agent/__init__.py` (currently empty placeholder)

- [ ] **Step 1: Write `__init__.py` with assembly, heartbeat, and startup**

```python
import asyncio
import random
from datetime import datetime, timedelta

from nonebot import get_driver

from .config import RUN_MODE, SHOW_PROCESS, SHOW_RAW_DEBUG
from .chat_window import chat_window
from .llm import query_ollama, handle_model_response
from . import handlers  # noqa: F401 — registers event handlers on import

global_state = {
    "last_decision": None,
    "last_processed_msg_time": None,
}


async def heartbeat_loop():
    print(f">>> 心跳模块已启动 | 当前模式: {RUN_MODE}")
    await asyncio.sleep(5)

    while True:
        current_latest_msg_time = chat_window.get_latest_msg_time()
        should_skip = False

        if global_state["last_decision"] == "WAIT":
            if current_latest_msg_time == global_state["last_processed_msg_time"]:
                should_skip = True

        if should_skip:
            if SHOW_PROCESS:
                print("[Heartbeat] Skipping (No New Msg)")
        else:
            if SHOW_PROCESS:
                print(
                    f"[Heartbeat] Processing... (Latest msg: {current_latest_msg_time})"
                )

            prompt_content = chat_window.build_prompt_content()

            if SHOW_RAW_DEBUG:
                print(
                    "\n" + "=" * 20 + " [Debug] Raw Prompt to LLM " + "=" * 20
                )
                print(prompt_content.strip())
                print("=" * 65 + "\n")
            elif SHOW_PROCESS:
                print("\n" + "-" * 20 + " [History Context] " + "-" * 20)
                print(chat_window.get_readable_history())
                print("-" * 57 + "\n")

            response_str = await query_ollama(prompt_content)

            if SHOW_RAW_DEBUG:
                print(
                    "\n"
                    + "=" * 20
                    + " [Debug] Raw Response from LLM "
                    + "=" * 20
                )
                print(str(response_str).strip())
                print("=" * 66 + "\n")

            decision = await handle_model_response(response_str)

            global_state["last_decision"] = decision
            global_state["last_processed_msg_time"] = current_latest_msg_time

        next_interval = random.randint(60, 180)
        if SHOW_PROCESS:
            next_time = datetime.now() + timedelta(seconds=next_interval)
            print(
                f"[Next Beat] Sleep {next_interval}s -> Wake at {next_time.strftime('%H:%M:%S')}"
            )
            print("_" * 60 + "\n")

        await asyncio.sleep(next_interval)


driver = get_driver()


@driver.on_startup
async def start_heartbeat_task():
    asyncio.create_task(heartbeat_loop())
```

- [ ] **Step 2: Verify the full package imports cleanly and the heartbeat startup is registered**

```bash
cd agent && python -c "from src.plugins import agent; print('Full package import OK'); print('chat_window:', agent.chat_window); print('global_state:', agent.global_state)"
```

- [ ] **Step 3: Commit**

```bash
git add agent/src/plugins/agent/__init__.py
git commit -m "refactor: create agent package __init__.py with assembly and heartbeat"
```

---

### Task 7: Replace old monolithic file with re-export shim

**Files:**
- Modify: `agent/src/plugins/agent.py` (replace with re-export shim)
- Delete: none (old file becomes thin re-export)

- [ ] **Step 1: Replace old `agent.py` with a backward-compatible re-export shim**

```python
# This file exists for backward compatibility.
# The plugin has been refactored into the agent/ package.
from .agent import *  # noqa: F401, F403
```

Wait — this would create a circular import because `agent.py` importing from `.agent` would import itself. We need a different approach. Instead, delete `agent.py` and verify NoneBot can still discover the plugin.

In NoneBot, plugins are discovered from `src/plugins/`. A directory `agent/` under `src/plugins/` with an `__init__.py` is automatically discovered as the `agent` plugin. The old `agent.py` file shadows the `agent/` package and must be deleted.

- [ ] **Step 1: Delete the old monolithic file**

```bash
rm agent/src/plugins/agent.py
```

- [ ] **Step 2: Verify the package is still importable without the old file**

```bash
cd agent && python -c "from src.plugins.agent import chat_window, global_state, heartbeat_loop; print('Package is working without agent.py')"
```

- [ ] **Step 3: Final verification — check all modules import without error**

```bash
cd agent && python -c "
from src.plugins.agent.config import *
from src.plugins.agent.user_map import *
from src.plugins.agent.chat_window import *
from src.plugins.agent.llm import *
from src.plugins.agent.handlers import *
from src.plugins.agent import *
print('All modules OK')
"
```

- [ ] **Step 4: Commit**

```bash
git rm agent/src/plugins/agent.py
git commit -m "refactor: remove old monolithic agent.py, replaced by agent/ package"
```

---

## Verification Checklist

After all tasks complete, confirm:

1. `git log --oneline` shows 7 commits for the refactoring
2. The package directory structure matches:
   ```
   agent/src/plugins/agent/
   ├── __init__.py
   ├── config.py
   ├── user_map.py
   ├── chat_window.py
   ├── handlers.py
   └── llm.py
   ```
3. `python -c "from src.plugins.agent import *"` succeeds
4. The old `agent.py` no longer exists
