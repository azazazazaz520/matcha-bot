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
