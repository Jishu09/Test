import time

from bot.config import Config

START_TIME = time.time()


def is_sudo(user_id: int) -> bool:
    return user_id in Config.SUDO_USERS


def is_owner(user_id: int) -> bool:
    return user_id == Config.OWNER_ID


def uptime() -> str:
    seconds = int(time.time() - START_TIME)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def get_media(message):
    """Return (media_object, media_type_str) for the first supported media in a message."""
    for kind in ("video", "document", "audio", "animation", "photo"):
        media = getattr(message, kind, None)
        if media:
            return media, kind
    return None, None


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]
