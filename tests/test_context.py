"""Tests for ContextManager persistence."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# ── patch NoneBot before anything from the matcha plugin gets imported ──
# The plugin's __init__.py calls require("nonebot_plugin_localstore") at module
# level and then creates the provider via _create_provider().  We inject
# lightweight mocks into sys.modules so that the import machinery short-circuits.
_mock_nonebot = MagicMock()
_mock_nonebot.get_driver.return_value.config = MagicMock()
sys.modules.setdefault("nonebot", _mock_nonebot)
sys.modules.setdefault("nonebot.plugin", MagicMock())
sys.modules.setdefault("nonebot.adapters", MagicMock())
sys.modules.setdefault("nonebot_plugin_localstore", MagicMock())

# Also mock the config so _create_provider() doesn't fail at import time.
# We provide valid-looking defaults so OpenAIProvider can be instantiated.
_mock_matcha_config = MagicMock()
_mock_matcha_config.matcha_nlp_provider = "openai"
_mock_matcha_config.matcha_nlp_api_key = "test-key"
_mock_matcha_config.matcha_nlp_base_url = "https://api.openai.com/v1"
_mock_matcha_config.matcha_nlp_model = "gpt-4o-mini"
_mock_matcha_config.matcha_nlp_respond_model = ""
sys.modules.setdefault("matcha.config", MagicMock())
sys.modules["matcha.config"].matcha_config = _mock_matcha_config

# Ensure the plugin source is importable
_plugin_root = Path(__file__).resolve().parents[1] / "src" / "plugins"
if str(_plugin_root) not in sys.path:
    sys.path.insert(0, str(_plugin_root))


@pytest.fixture
def data_dir() -> Generator[Path, Any, None]:
    """Create a temporary directory for context storage."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def context_manager_cls() -> type:
    """Return the ContextManager class."""
    from matcha.context import ContextManager

    return ContextManager


def test_persists_and_restores_context(
    context_manager_cls: type, data_dir: Path
) -> None:
    """ContextManager should persist messages to disk and restore them on reload."""
    # Create first instance and add messages
    cm1 = context_manager_cls(max_rounds=10, data_dir=data_dir)
    cm1.add_message("group_123_user_456", "user", "你好")
    cm1.add_message("group_123_user_456", "assistant", "嗨~")

    # Verify file was written
    session_file = data_dir / "group_123_user_456.json"
    assert session_file.exists()

    # Simulate restart: create a new ContextManager with the same data_dir
    cm2 = context_manager_cls(max_rounds=10, data_dir=data_dir)

    # Should restore messages from disk
    context = cm2.get_context("group_123_user_456")
    assert len(context) == 2
    assert context[0] == {"role": "user", "content": "你好"}
    assert context[1] == {"role": "assistant", "content": "嗨~"}


def test_clear_removes_disk_file(
    context_manager_cls: type, data_dir: Path
) -> None:
    """clear() should delete the session file from disk."""
    cm = context_manager_cls(max_rounds=10, data_dir=data_dir)
    cm.add_message("group_1_user_2", "user", "hello")
    cm.add_message("group_1_user_2", "assistant", "hi")

    session_file = data_dir / "group_1_user_2.json"
    assert session_file.exists()

    cm.clear("group_1_user_2")
    assert not session_file.exists()
    assert cm.get_context("group_1_user_2") == []


def test_truncates_on_load(
    context_manager_cls: type, data_dir: Path
) -> None:
    """When messages exceed max_rounds, only the latest should be kept."""
    cm1 = context_manager_cls(max_rounds=2, data_dir=data_dir)
    # Add 3 rounds = 6 messages
    for i in range(3):
        cm1.add_message("sess", "user", f"user-msg-{i}")
        cm1.add_message("sess", "assistant", f"bot-msg-{i}")

    # Reload — should only keep last 2 rounds (4 messages)
    cm2 = context_manager_cls(max_rounds=2, data_dir=data_dir)
    ctx = cm2.get_context("sess")
    assert len(ctx) == 4
    # First two rounds dropped
    assert ctx[0]["content"] == "user-msg-1"
    assert ctx[2]["content"] == "user-msg-2"


def test_unknown_session_returns_empty(
    context_manager_cls: type, data_dir: Path
) -> None:
    """Querying a session that has never existed should return an empty list."""
    cm = context_manager_cls(data_dir=data_dir)
    assert cm.get_context("nonexistent") == []


def test_no_data_dir_still_works(
    context_manager_cls: type,
) -> None:
    """ContextManager without data_dir should work as before (no persistence)."""
    cm = context_manager_cls(max_rounds=10)
    cm.add_message("sess", "user", "hello")
    assert cm.get_context("sess") == [{"role": "user", "content": "hello"}]
