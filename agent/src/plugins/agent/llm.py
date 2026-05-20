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


async def handle_model_response(raw_text: Optional[str]) -> str:
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
