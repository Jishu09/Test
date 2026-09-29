"""
Central error reporting: one logging.Handler, attached to the root logger,
catches every ERROR-level (and above) log record anywhere in the process —
including the ones Pyrogram's own dispatcher logs when a handler raises an
uncaught exception — and mirrors it to the bot's LOG_CHANNEL as a single,
consistently-styled message instead of the mix of ad-hoc `send_message`
calls scattered around the codebase.

Using a logging.Handler instead of wrapping every plugin handler means new
plugins get this for free with zero extra code, and it also catches errors
pyrogram raises internally that our own code never sees.
"""

import asyncio
import html
import logging
import traceback
from datetime import datetime, timezone

MAX_BODY_LEN = 3500  # keep well under Telegram's 4096-char message cap


class TelegramLogHandler(logging.Handler):
    def __init__(self, client, log_channel: int, level=logging.ERROR):
        super().__init__(level)
        self.client = client
        self.log_channel = log_channel

    def emit(self, record: logging.LogRecord):
        if not self.log_channel or not self.client:
            return
        # Never let our own send attempt re-enter and cause log spam/recursion.
        if getattr(record, "_from_telegram_log_handler", False):
            return
        try:
            text = self._format_record(record)
        except Exception:
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._send(text))
        except RuntimeError:
            pass  # no running loop (e.g. during shutdown) — drop it

    def _format_record(self, record: logging.LogRecord) -> str:
        title = html.escape(f"{record.levelname} — {record.name}")
        message = html.escape(record.getMessage())

        body_parts = [message]
        if record.exc_info:
            tb = "".join(traceback.format_exception(*record.exc_info))
            body_parts.append(html.escape(tb))
        body = "\n\n".join(p for p in body_parts if p.strip())
        if len(body) > MAX_BODY_LEN:
            body = body[:MAX_BODY_LEN] + "\n… (truncated)"

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            f"🛑 <b>{title}</b>\n\n"
            f"<blockquote expandable>{body}</blockquote>\n\n"
            f"🕒 <code>{ts}</code>"
        )

    async def _send(self, text: str):
        try:
            from pyrogram.enums import ParseMode

            await self.client.send_message(
                self.log_channel, text, parse_mode=ParseMode.HTML
            )
        except Exception:
            # A broken log channel must never crash the bot or recurse.
            pass


def attach(client, log_channel: int, level=logging.ERROR):
    """Attach the handler to the root logger. Call once, after the Client
    is created (any logger anywhere in the app propagates up to root by
    default, so this alone covers everything)."""
    if not log_channel:
        return None
    handler = TelegramLogHandler(client, log_channel, level=level)
    logging.getLogger().addHandler(handler)
    return handler
