import os
import logging

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from pyrogram.errors import MessageNotModified, MessageIdInvalid, FloodWait

from bot.caption_engine import (
    parse_filename,
    merge_with_fallback,
    build_caption,
    apply_remove_words,
    apply_replace_words,
    apply_prefix_suffix,
    reverse_caption,
    apply_font,
    human_size,
    human_duration,
    resolve_title,
)
from bot.config import Config
from bot.database import db
from utils.buttons import parse_custom_buttons
from utils.helpers import get_media
from utils.queue_manager import edit_queue

logger = logging.getLogger(__name__)


def _extract_meta(message: Message, media, kind: str, channel_title: str) -> dict:
    caption_obj = message.caption
    meta = {
        "filename": "",
        "filesize": getattr(media, "file_size", 0) or 0,
        "duration": getattr(media, "duration", 0) or 0,
        "height": getattr(media, "height", "") or "",
        "width": getattr(media, "width", "") or "",
        "mime_type": getattr(media, "mime_type", "") or "",
        "artist": getattr(media, "performer", "") or "",
        "channel": channel_title,
        "caption": str(caption_obj) if caption_obj else "",
        "html_caption": getattr(caption_obj, "html", str(caption_obj)) if caption_obj else "",
    }

    if kind == "audio":
        meta["filename"] = getattr(media, "file_name", None) or getattr(media, "title", None) or f"audio_{message.id}"
        meta["title"] = getattr(media, "title", "") or meta["filename"]
    else:
        meta["filename"] = getattr(media, "file_name", None) or f"{kind}_{message.id}"

    meta["extension"] = os.path.splitext(meta["filename"])[1].lstrip(".").upper()
    return meta


async def _process_and_caption(client: Client, message: Message):
    """The actual auto-caption pipeline (parsing, TMDB, caption building,
    the Telegram edit). This runs *inside* the per-chat queue worker, one
    message at a time, in the exact order messages were queued — see
    auto_caption_handler below for why that guarantees serial order."""
    chat = await db.get_channel(message.chat.id)
    if not chat or not chat.get("auto_caption", True):
        return

    media, kind = get_media(message)
    if not media or kind not in chat.get("media_filter", ["video", "document", "audio"]):
        return

    file_unique_id = getattr(media, "file_unique_id", None)

    meta = _extract_meta(message, media, kind, chat.get("title", ""))
    custom_regex = chat.get("custom_regex", {})
    # Filename first; if it doesn't yield useful fields, fall back to the
    # file's own caption text (many uploaders put Title/Episode/Season/
    # Quality on separate lines there instead of in the filename).
    parsed = parse_filename(meta["filename"], custom_regex, fallback_text=meta.get("caption"))

    last_meta = chat.get("last_meta", {})

    # --- TMDB title resolution (cached, type-aware, confidence-checked) ---
    raw_query = parsed.get("title")
    if raw_query and chat.get("use_tmdb", True) and getattr(Config, "TMDB_API_KEY", ""):
        is_series = bool(parsed.get("season") or parsed.get("episode"))
        try:
            parsed["title"] = await resolve_title(
                raw_query,
                Config.TMDB_API_KEY,
                is_series=is_series,
                year=parsed.get("year"),
            )
        except Exception as e:
            logger.warning(f"TMDB resolution failed, using regex title instead: {e}")
            parsed["title"] = raw_query

    merged = merge_with_fallback(parsed, last_meta)
    meta.update({k: v for k, v in merged.items() if v})

    raw_caption = chat.get("caption")
    template = raw_caption or Config.DEFAULT_CAPTION
    caption = build_caption(template, meta)

    caption = apply_remove_words(caption, chat.get("remove_words", []))
    caption = apply_replace_words(caption, chat.get("replace_words", {}))
    caption = apply_prefix_suffix(caption, chat.get("prefix", ""), chat.get("suffix", ""))

    if chat.get("caption_reversal"):
        caption = reverse_caption(caption)
    caption = apply_font(caption, chat.get("caption_font", "normal"))

    if chat.get("media_details") and kind in ("video", "audio", "document", "animation"):
        details = []
        if meta.get("width") and meta.get("height"):
            details.append(f"📐 Resolution: {meta['width']}x{meta['height']}")
        if meta.get("duration"):
            details.append(f"⏱ Duration: {human_duration(meta['duration'])}")
        if meta.get("filesize"):
            details.append(f"💾 Size: {human_size(meta['filesize'])}")
        if meta.get("mime_type"):
            details.append(f"🎞 Type: {meta['mime_type']}")
        if details:
            caption += "\n\n" + "\n".join(details)

    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    markup = parse_custom_buttons(chat.get("custom_buttons"))

    try:
        await client.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message.id,
            caption=caption,
            reply_markup=markup,
        )
        logger.info(f"Successfully edited caption for message: {message.id}")
    except (MessageNotModified, MessageIdInvalid):
        pass
    except Exception as e:
        if "ENTITY_BOUNDS_INVALID" in str(e) or "entity bounds" in str(e).lower():
            try:
                await client.edit_message_caption(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    caption=caption,
                    reply_markup=markup,
                    parse_mode=ParseMode.DISABLED,
                )
                logger.info(f"Successfully edited caption (Fallback to Plain Text) for message: {message.id}")
            except Exception as fallback_error:
                if isinstance(fallback_error, FloodWait):
                    raise
                logger.error(
                    f"Fallback edit failed for message {message.id} in chat {message.chat.id}: {fallback_error}"
                )
                return
        else:
            # Let FloodWait bubble up so the queue manager retries it;
            # anything else is a genuine failure — the central log handler
            # (utils/telegram_log_handler.py) mirrors this to LOG_CHANNEL.
            if isinstance(e, FloodWait):
                raise
            logger.error(f"Failed to edit caption for message {message.id} in chat {message.chat.id}: {e}")
            return

    if file_unique_id:
        await db.mark_file_processed(file_unique_id, message.chat.id)
    await db.update_last_meta(message.chat.id, merged)


def register(app: Client):
    @app.on_message(
        filters.channel
        & (filters.video | filters.document | filters.audio | filters.animation | filters.photo),
        group=1,
    )
    async def auto_caption_handler(client: Client, message: Message):
        # Submit to this channel's queue as the very first action, before any
        # `await` runs. An `async def` call with no internal await points
        # never yields control back to the event loop, so as long as nothing
        # here suspends first, insertion order into the queue matches the
        # order Telegram delivered these updates — regardless of how long
        # any individual file's TMDB lookup / caption building later takes.
        # All of that heavy, variable-latency work now happens *inside* the
        # queue worker (see _process_and_caption above), one file at a time,
        # so files are always captioned in upload order and none are skipped.
        await edit_queue.submit(message.chat.id, _process_and_caption, client, message)
