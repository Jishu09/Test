import os

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import Message

from bot.config import Config
from bot.database import db
from utils.helpers import is_sudo


async def _is_channel_admin(client: Client, message: Message) -> bool:
    """Admins posting directly in a channel often show up with from_user=None
    (posted 'as the channel'). Only real admins can post at all in that case,
    so we allow it. If from_user IS present, verify admin status explicitly."""
    if message.from_user is None:
        return True
    if is_sudo(message.from_user.id):
        return True
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


def register(app: Client):
    @app.on_message(filters.command("connect") & filters.channel)
    async def connect_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        created = await db.add_channel(
            message.chat.id,
            message.chat.title or "Unknown",
            message.from_user.id if message.from_user else 0,
        )
        text = (
            "✅ **Channel connected!** Auto-captioning is now active."
            if created
            else "ℹ️ This channel is already connected."
        )
        await message.reply_text(text)

    @app.on_message(filters.command("disconnect") & filters.channel)
    async def disconnect_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        await db.remove_channel(message.chat.id)
        await message.reply_text("🗑 **Channel disconnected.**")

    @app.on_message(filters.command("setcaption") & filters.channel)
    async def setcaption_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2 and not message.reply_to_message:
            await message.reply_text(
                "⚠️ Usage: `/setcaption {title} S{season}E{episode} [{quality}]`\n\n"
                "Available placeholders: `{filename}` `{filesize}` `{duration}` "
                "`{title}` `{season}` `{episode}` `{quality}` `{language}` `{year}` "
                "`{source}` `{extension}` `{channel}`",
            )
            return
        template = message.text.split(None, 1)[1] if len(message.command) >= 2 else message.reply_to_message.text
        await db.set_caption(message.chat.id, template)
        await message.reply_text("✅ **Caption template updated for this channel.**")

    @app.on_message(filters.command("mycaption") & filters.channel)
    async def mycaption_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        caption = await db.get_caption(message.chat.id)
        await message.reply_text(f"📋 **Current template:**\n\n`{caption}`")

    @app.on_message(filters.command("resetcaption") & filters.channel)
    async def resetcaption_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        await db.set_caption(message.chat.id, None)
        await message.reply_text("♻️ **Caption template reset to default.**")

    @app.on_message(filters.command("autocaption") & filters.channel)
    async def autocaption_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
            await message.reply_text("⚠️ Usage: `/autocaption on` or `/autocaption off`")
            return
        state = message.command[1].lower() == "on"
        await db.toggle_auto_caption(message.chat.id, state)
        await message.reply_text(
            f"✅ Auto-caption is now **{'ON' if state else 'OFF'}** for this channel."
        )

    @app.on_message(filters.command("filter") & filters.channel)
    async def filter_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2:
            await message.reply_text(
                "⚠️ Usage: `/filter video,document,audio`"
            )
            return
        types = [t.strip().lower() for t in message.text.split(None, 1)[1].split(",")]
        valid = {"video", "document", "audio", "animation", "photo"}
        types = [t for t in types if t in valid]
        if not types:
            await message.reply_text("⚠️ No valid media types given.")
            return
        await db.set_media_filter(message.chat.id, types)
        await message.reply_text(f"✅ Media filter set to: `{', '.join(types)}`")

    @app.on_message(filters.command("setregex") & filters.channel)
    async def setregex_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 3:
            await message.reply_text(
                "⚠️ Usage: `/setregex <field> <pattern>`\n"
                "Fields: `season` `episode` `quality` `language` `year` `source` `title`\n"
                "Pattern must include a named group matching the field, e.g.\n"
                "`/setregex quality (?P<quality>4K|2K)`",
            )
            return
        field = message.command[1].lower()
        pattern = message.text.split(None, 2)[2]
        valid_fields = {"season", "episode", "quality", "language", "year", "source", "title"}
        if field not in valid_fields:
            await message.reply_text(f"⚠️ Invalid field. Choose from: {', '.join(valid_fields)}")
            return
        await db.add_custom_regex(message.chat.id, field, pattern)
        await message.reply_text(f"✅ Custom regex saved for `{field}`.")

    @app.on_message(filters.command("addbutton") & filters.channel)
    async def addbutton_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2:
            await message.reply_text(
                "⚠️ Usage: `/addbutton [Text][buttonurl:https://example.com]`"
            )
            return
        raw = message.text.split(None, 1)[1]
        await db.set_custom_buttons(message.chat.id, raw)
        await message.reply_text("✅ **Button saved.**")

    @app.on_message(filters.command("delbutton") & filters.channel)
    async def delbutton_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        await db.set_custom_buttons(message.chat.id, None)
        await message.reply_text("🗑 **Button removed.**")

    @app.on_message(filters.command("removeword") & filters.channel)
    async def removeword_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/removeword <word or phrase>`")
            return
        word = message.text.split(None, 1)[1]
        await db.add_remove_word(message.chat.id, word)
        await message.reply_text(f"✅ Added `{word}` to the remove list.")

    @app.on_message(filters.command("replaceword") & filters.channel)
    async def replaceword_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 3:
            await message.reply_text("⚠️ Usage: `/replaceword <old> <new>`")
            return
        _, rest = message.text.split(None, 1)
        parts = rest.split(None, 1)
        if len(parts) < 2:
            await message.reply_text("⚠️ Usage: `/replaceword <old> <new>`")
            return
        await db.add_replace_word(message.chat.id, parts[0], parts[1])
        await message.reply_text(f"✅ `{parts[0]}` → `{parts[1]}` saved.")

    @app.on_message(filters.command("clearwords") & filters.channel)
    async def clearwords_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        await db.clear_remove_words(message.chat.id)
        await db.clear_replace_words(message.chat.id)
        await message.reply_text("🗑 **Word lists cleared.**")

    @app.on_message(filters.command("setprefix") & filters.channel)
    async def setprefix_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/setprefix <text>`")
            return
        await db.set_prefix(message.chat.id, message.text.split(None, 1)[1])
        await message.reply_text("✅ **Prefix saved.**")

    @app.on_message(filters.command("delprefix") & filters.channel)
    async def delprefix_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        await db.set_prefix(message.chat.id, "")
        await message.reply_text("🗑 **Prefix removed.**")

    @app.on_message(filters.command("setsuffix") & filters.channel)
    async def setsuffix_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/setsuffix <text>`")
            return
        await db.set_suffix(message.chat.id, message.text.split(None, 1)[1])
        await message.reply_text("✅ **Suffix saved.**")

    @app.on_message(filters.command("delsuffix") & filters.channel)
    async def delsuffix_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        await db.set_suffix(message.chat.id, "")
        await message.reply_text("🗑 **Suffix removed.**")

    @app.on_message(filters.command("captionreversal") & filters.channel)
    async def captionreversal_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
            await message.reply_text("⚠️ Usage: `/captionreversal on` or `/captionreversal off`")
            return
        state = message.command[1].lower() == "on"
        await db.toggle_caption_reversal(message.chat.id, state)
        await message.reply_text(f"✅ Caption reversal: **{'ON' if state else 'OFF'}**")

    @app.on_message(filters.command("mediadetails") & filters.channel)
    async def mediadetails_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
            await message.reply_text("⚠️ Usage: `/mediadetails on` or `/mediadetails off`")
            return
        state = message.command[1].lower() == "on"
        await db.toggle_media_details(message.chat.id, state)
        await message.reply_text(f"✅ Media details: **{'ON' if state else 'OFF'}**")

    @app.on_message(filters.command("captionfont") & filters.channel)
    async def captionfont_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        valid = {"normal", "bold", "italic", "mono", "underline"}
        if len(message.command) < 2 or message.command[1].lower() not in valid:
            await message.reply_text(f"⚠️ Usage: `/captionfont <{'|'.join(valid)}>`")
            return
        await db.set_caption_font(message.chat.id, message.command[1].lower())
        await message.reply_text(f"✅ Caption font set to **{message.command[1].lower()}**.")

    @app.on_message(filters.command("usetmdb") & filters.channel)
    async def usetmdb_cmd(client: Client, message: Message):
        if not await _is_channel_admin(client, message):
            return
        if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
            await message.reply_text("⚠️ Usage: `/usetmdb on` or `/usetmdb off`")
            return
        state = message.command[1].lower() == "on"
        await db.toggle_use_tmdb(message.chat.id, state)
        await message.reply_text(
            f"✅ TMDB title lookup: **{'ON' if state else 'OFF'}**\n"
            + (
                "Titles will now be verified against TMDB (cached, so repeat episodes are instant)."
                if state
                else "Titles will use the filename-only regex parser (fastest, no external calls)."
            ),
        )

    @app.on_message(filters.command("cleartmdbcache") & filters.private)
    async def cleartmdbcache_cmd(client: Client, message: Message):
        from utils.helpers import is_sudo

        if not is_sudo(message.from_user.id):
            return
        count = await db.clear_tmdb_cache()
        await message.reply_text(f"🗑 Cleared **{count}** cached TMDB title(s).")
