from __future__ import annotations

import json
from collections import defaultdict
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from .provider.base import ChatMessage

DEFAULT_MAX_ROUNDS = 10


class ContextManager:
    """内存中的对话上下文管理器，key 为 session_id（如 "group_123_user_456"）。

    可选参数 ``data_dir`` 用于持久化上下文到磁盘。
    传入后每次 add_message 都会自动写入 JSON 文件，
    新建实例时可通过 get_context 从磁盘恢复历史对话。
    """

    def __init__(
        self,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        data_dir: Path | None = None,
    ) -> None:
        # 内存存储：session_id → 消息列表
        self._store: dict[str, list[ChatMessage]] = defaultdict(list)
        self._max_rounds = max_rounds
        # 持久化目录，为 None 时不启用磁盘存储（向后兼容）
        self._data_dir = data_dir
        if self._data_dir is not None:
            self._data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def session_id(*, group_id: str | None, user_id: str) -> str:
        if group_id:
            return f"group_{group_id}_user_{user_id}"
        return f"private_{user_id}"

    # ------------------------------------------------------------------
    # 持久化辅助方法
    # ------------------------------------------------------------------

    def _session_file(self, session: str) -> Path:
        """返回 session 对应的 JSON 文件路径。

        调用方必须确保 ``self._data_dir`` 不为 None。
        """
        # session key 仅含字母数字和下划线，可直接作为文件名
        assert self._data_dir is not None  # 所有调用方在使用前已判空
        return self._data_dir / f"{session}.json"

    def _ensure_loaded(self, session: str) -> None:
        """首次访问时从磁盘懒加载会话历史。"""
        if self._data_dir is not None and session not in self._store:
            self._load_session(session)

    def _load_session(self, session: str) -> None:
        """从 JSON 文件加载 session 的消息到内存。"""
        if session in self._store:
            return  # 已在内存中，无需重复加载
        file = self._session_file(session)
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                # 加载时按 max_rounds 截断，防止旧数据无限膨胀
                limit = self._max_rounds * 2
                self._store[session] = data[-limit:]
        except (FileNotFoundError, json.JSONDecodeError):
            self._store[session] = []

    def _save_session(self, session: str) -> None:
        """将当前 session 的内存数据写入 JSON 文件。"""
        file = self._session_file(session)
        # ensure_ascii=False 保留中文可读性，indent=2 方便调试
        file.write_text(
            json.dumps(self._store[session], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def add_message(self, session: str, role: str, content: str) -> None:
        # 首次访问该 session 时从磁盘懒加载历史
        self._ensure_loaded(session)

        self._store[session].append({"role": role, "content": content})
        # 每轮 = user + assistant 两条消息，保留 max_rounds 轮
        limit = self._max_rounds * 2
        if len(self._store[session]) > limit:
            self._store[session] = self._store[session][-limit:]

        # 写入磁盘持久化
        if self._data_dir is not None:
            self._save_session(session)

    def get_context(self, session: str) -> list[ChatMessage]:
        # 首次访问该 session 时从磁盘懒加载历史
        self._ensure_loaded(session)
        return list(self._store[session])

    def clear(self, session: str) -> None:
        """清除指定 session 的内存和磁盘数据。"""
        self._store.pop(session, None)
        if self._data_dir is not None:
            file = self._session_file(session)
            with suppress(OSError):
                file.unlink(missing_ok=True)
