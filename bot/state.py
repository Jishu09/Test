"""
Lightweight in-memory state store for multi-step PM conversations
(e.g. "waiting for caption text for channel X"). Not persisted across
restarts by design — these are short-lived UX flows, not data.
"""

WAITING = {}  # user_id -> {"action": str, "chat_id": int, ...}


def set_wait(user_id: int, action: str, **extra):
    WAITING[user_id] = {"action": action, **extra}


def get_wait(user_id: int):
    return WAITING.get(user_id)


def clear_wait(user_id: int):
    WAITING.pop(user_id, None)
