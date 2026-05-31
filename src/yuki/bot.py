"""友希（Yuki）的 NoneBot 插件层"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

import nonebot
from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent

from . import response
from .response import ChatRecord

# ---- 配置  ----
TARGET_GROUP_ID = 940123987  # 目标群号
MAX_HISTORY = 50  
TICK_INTERVAL = 60  

# ---- 内存状态 ----
_history: list[ChatRecord] = []
_new_msg_count = 0

driver = get_driver()

def log(msg: str) -> None:
    """带时间戳的简易日志打印"""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [yuki.bot] {msg}")

def _extract_text(event: GroupMessageEvent) -> str:
    parts = [seg.data.get("text", "") for seg in event.get_message() if seg.type == "text"]
    return "".join(parts).strip()

def _is_at_me(event: GroupMessageEvent) -> bool:
    """精准检测：消息是否 @ 了机器人"""
    if event.is_tome():
        return True
    self_id = str(event.self_id)
    for seg in event.original_message:
        if seg.type == "at" and str(seg.data.get("qq", "")) == self_id:
            return True
    return False

def _sender_name(event: GroupMessageEvent) -> str:
    card = event.sender.card
    nickname = event.sender.nickname
    return card or nickname or str(event.user_id)

async def _send_reply(reply: str) -> None:
    """封装的发送函数，发送并将回复写入历史"""
    log(f"准备发送回复: {reply[:20]}...")
    try:
        bot = nonebot.get_bot()
    except Exception as e:
        log(f"❌ 暂无可用 bot 连接，跳过发送: {e}")
        return

    try:
        await bot.send_group_msg(group_id=TARGET_GROUP_ID, message=reply)
        log("✅ 回复发送成功！")
    except Exception as e:
        log(f"❌ 发送群消息失败: {e}")
        return

    _history.append(ChatRecord(role="assistant", name=None, content=reply))
    if len(_history) > MAX_HISTORY:
        del _history[:-MAX_HISTORY]

# 监听目标群的所有消息
group_listener = on_message(priority=10, block=False)

@group_listener.handle()
async def collect_message(event: GroupMessageEvent) -> None:
    global _new_msg_count

    # 1. 群号过滤
    if event.group_id != TARGET_GROUP_ID:
        return

    # 2. 自身消息过滤
    if str(event.user_id) == str(event.self_id):
        return

    log(f"收到来自 {event.user_id} 的消息")

    # 3. 提前提取文本并入库（作为上下文）
    text = _extract_text(event)
    if text:
        _history.append(
            ChatRecord(role="user", name=_sender_name(event), content=text)
        )
        if len(_history) > MAX_HISTORY:
            del _history[:-MAX_HISTORY]

    # 4. 判断是否被 @
    if _is_at_me(event):
        log("⚡ 触发 [立即回复]：机器人被 @ 了！开始实时请求 AI...")
        # 复制一份当前完整的上下文历史
        current_history = list(_history)
        
        # 异步调用 API 生成回复（在当前消息协程中直接处理，实现秒回）
        reply = await response.reply_from_history(current_history)
        if reply:
            await _send_reply(reply)
        else:
            log("❌ [立即回复] 失败：API 异常未返回文本")
            
        # 被 @ 后的消息不计入常规轮询的计数，避免下一分钟重复触发普通回复
        return

    # 5. 常规消息：计入周期计数器，等待每分钟定时结算
    if text:
        _new_msg_count += 1
        log(f"=> 闲聊消息已入库。当前周期缓冲消息数: {_new_msg_count}")


async def _tick_once() -> None:
    """整分钟结算逻辑（此时已不再处理被 @ 的情况）"""
    global _new_msg_count

    count = _new_msg_count
    history = list(_history)

    # 立即清零，开始新周期
    _new_msg_count = 0

    log(f"=== 开始整分钟结算 (闲聊新消息: {count}) ===")

    # 交给 tick（内部含「>15 条 + 决策模型」逻辑）
    reply = await response.tick(count, history)

    if reply:
        log("=> 闲聊触发决策通过，进入发送流程。")
        await _send_reply(reply)
    else:
        log("=> 本次结算结果：闲聊未触发回复 (未达阈值、决策否决或 API 异常)")


async def _tick_loop() -> None:
    now = time.time()
    sleep_time = TICK_INTERVAL - (now % TICK_INTERVAL)
    log(f"启动定时器，将在 {sleep_time:.1f} 秒后进行首次对齐检测...")
    await asyncio.sleep(sleep_time)
    
    while True:
        try:
            await _tick_once()
        except Exception as e:
            log(f"❌ 周期检测异常: {e}")
        await asyncio.sleep(TICK_INTERVAL)


@driver.on_startup
async def _start_tick_loop() -> None:
    log("插件启动，建立后台检测循环。")
    asyncio.create_task(_tick_loop())