# Agent Plugin Refactor Design

## Goal

Split the monolithic `agent/src/plugins/agent.py` (394 lines) into a Python package
under `agent/src/plugins/agent/` with 6 modules, each responsible for a single
concern. Behavior is preserved; only module boundaries are changed.

## Directory Structure

```
agent/src/plugins/agent/
├── __init__.py      # Entry point + assembly + heartbeat + driver startup
├── config.py        # All config constants and mode flags
├── user_map.py      # QQ number ↔ anonymous ID bidirectional mapping
├── chat_window.py   # ChatWindowManager — message context window
├── handlers.py      # NoneBot event handlers (listener, bot hook, debug command)
└── llm.py           # Ollama API call + response parsing + message sending
```

## Module Details

### config.py
- Runs at import time; no dependencies on other agent modules
- Contains: `RUN_MODE`, `REPLY_GROUP_ID`, `LISTEN_GROUP_IDS`, `SELF_KEYWORDS`,
  `DATA_DIR`, `USER_MAP_FILE_PATH`, `MAX_WINDOW_SIZE`, `TIMEOUT_MINUTES`,
  `OLLAMA_API_URL`, `OLLAMA_MODEL`
- Derived flags: `CAN_SEND_REAL_MSG`, `SHOW_PROCESS`, `SHOW_RAW_DEBUG`
- Creates `DATA_DIR` if missing

### user_map.py
- Private module-level `user_map: dict`
- Public: `load_user_map()`, `save_user_map()`, `get_anonymous_id()`,
  `get_real_id_by_anon()`
- Auto-loads on import
- `resolve_self_mention()` moves to handlers (it is message preprocessing)

### chat_window.py
- Class `ChatWindowManager` — unchanged logic
- Internal `_should_clear()` kept private
- `add_message()`, `build_prompt_content()`, `get_readable_history()`,
  `get_latest_msg_time()` are the public API
- XML escaping extracted to `_escape_xml()` static method
- Global instance is created in `__init__.py`, not here

### handlers.py
- `resolve_self_mention(msg, target) -> Tuple[str, str]` — keyword → "你" + target → "Me"
- `on_message` handler — message recording + keyword preprocessing
- `Bot.on_calling_api` hook — captures bot's own outgoing messages
- `on_command("force_beat")` debug command
- Log persistence logic extracted into a helper function

### llm.py
- `query_ollama(content_text) -> Optional[str]` — calls Ollama API, returns raw
- `handle_model_response(raw_text, bot) -> str` — parses `<think>/<choice>/<reply>`,
  sends messages via the passed-in `bot`, returns decision string ("SEND" / "WAIT")
- Logger output controlled by config flags (`SHOW_PROCESS`, `SHOW_RAW_DEBUG`)

### __init__.py
- Imports and re-exports all sub-modules
- Creates global instances: `chat_window = ChatWindowManager()`,
  `global_state = {...}`
- Contains `heartbeat_loop()` coroutine — the core loop unchanged, calls into
  `chat_window`, `query_ollama`, `handle_model_response`
- Registers `driver.on_startup` to spawn heartbeat task

## Dependencies (acyclic)

```
__init__ → handlers → llm → chat_window → user_map → config
                                      ↘ user_map
```

- `config` depends on nothing
- `user_map` depends on `config`
- `chat_window` depends on `config`
- `llm` depends on `config`, `user_map`
- `handlers` depends on `config`, `user_map`, `chat_window`
- `__init__` depends on everything (assembly)
