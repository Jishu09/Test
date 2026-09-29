import os
from dotenv import load_dotenv

load_dotenv()


def _int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _bool(val, default=False):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


class Config:
    API_ID = _int(os.environ.get("API_ID"))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    MONGO_URI = os.environ.get("MONGO_URI", "")
    DB_NAME = os.environ.get("DB_NAME", "AutoCaptionBotPro")

    OWNER_ID = _int(os.environ.get("OWNER_ID"))
    SUDO_USERS = [
        _int(x) for x in os.environ.get("SUDO_USERS", "").split() if x.strip()
    ]
    if OWNER_ID and OWNER_ID not in SUDO_USERS:
        SUDO_USERS.append(OWNER_ID)

    LOG_CHANNEL = _int(os.environ.get("LOG_CHANNEL"))

    FSUB_CHANNELS = [
        _int(x) for x in os.environ.get("FSUB_CHANNELS", "").split(",") if x.strip()
    ]
    FSUB_JOIN_REQUEST = _bool(os.environ.get("FSUB_JOIN_REQUEST"), True)

    DEFAULT_CAPTION = os.environ.get(
        "DEFAULT_CAPTION",
        "{filename}\n\n**Powered by:** {channel}",
    )

    TIMEZONE = os.environ.get("TIMEZONE", "Asia/Dhaka")
    PORT = _int(os.environ.get("PORT"), 8080)

    BOT_NAME = os.environ.get("BOT_NAME", "AutoCaptionBot")
    SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "")
    UPDATES_CHANNEL = os.environ.get("UPDATES_CHANNEL", "")

    START_PICS = [
        x.strip() for x in os.environ.get("START_PICS", "").split(",") if x.strip()
    ]
    FSUB_PIC = os.environ.get("FSUB_PIC", "").strip()

    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")



def validate_config():
    missing = []
    for key in ("API_ID", "API_HASH", "BOT_TOKEN", "MONGO_URI", "OWNER_ID"):
        if not getattr(Config, key):
            missing.append(key)
    if missing:
        raise SystemExit(
            f"[CONFIG ERROR] Missing required environment variables: {', '.join(missing)}\n"
            f"Please check your .env file / deployment variables."
        )
