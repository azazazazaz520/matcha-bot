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
