import json
import re
from datetime import datetime
from typing import Tuple

from nonebot import on_message, on_command
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.exception import ActionFailed

from .config import REPLY_GROUP_ID, LISTEN_GROUP_IDS, SELF_KEYWORDS, DATA_DIR, RUN_MODE, SHOW_PROCESS, SHOW_RAW_DEBUG
from .chat_window import chat_window
from .user_map import get_anonymous_id
from .llm import query_ollama, handle_model_response


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
