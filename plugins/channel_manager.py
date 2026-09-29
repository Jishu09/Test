from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

from bot.database import db
from bot.state import set_wait, get_wait, clear_wait
from utils.buttons import primary_btn, success_btn, danger_btn, plain_btn
from utils.helpers import is_sudo
from plugins.script import CAPTION_GUIDE, BUTTON_GUIDE, WORDS_GUIDE

FONT_OPTIONS = [
    ("normal", "🔤 Normal"),
    ("bold", "𝐁 Bold"),
    ("italic", "𝑰 Italic"),
    ("mono", "🖥 Monospace"),
    ("underline", "🔻 Underline"),
]

# ---------------------------------------------------------------------------
# Core UI Helper
# ---------------------------------------------------------------------------
async def safe_edit(cq: CallbackQuery, text: str, markup: InlineKeyboardMarkup):
    """Edits the panel message in place whenever possible. Deliberately
    never calls message.delete() — a bot can't always delete its own
    messages (Telegram returns MESSAGE_DELETE_FORBIDDEN in some contexts,
    e.g. via certain session/business setups), so instead this falls back
    to sending a fresh message, which works everywhere."""
    is_media = bool(cq.message.photo or cq.message.video or cq.message.animation)

    if is_media and len(text) > 1024:
        # Telegram media captions are capped at 1024 chars — this text is
        # longer, so it can't be edited in place. Send it as a new message
        # instead of touching the old one.
        await cq.message.reply_text(text, reply_markup=markup)
        return

    try:
        if is_media:
            await cq.message.edit_caption(caption=text, reply_markup=markup)
        else:
            await cq.message.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass
    except Exception:
        # Any other edit failure (stale message, permissions, etc.) —
        # never let the callback crash; just deliver the content fresh.
        await cq.message.reply_text(text, reply_markup=markup)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------
async def _can_manage(user_id: int, chat_id: int) -> bool:
    """Only the person who connected a channel can see/manage it here —
    intentionally no sudo/owner bypass, so one admin's channels are never
    visible to another admin just because they're also sudo."""
    ch = await db.get_channel(chat_id)
    if not ch:
        return False
    return ch.get("added_by") == user_id


async def _user_channels(user_id: int):
    channels = [c async for c in await db.get_all_channels()]
    return [c for c in channels if c.get("added_by") == user_id]


# ---------------------------------------------------------------------------
# Menu renderers
# ---------------------------------------------------------------------------
async def render_list(user_id: int):
    channels = await _user_channels(user_id)
    rows = [[plain_btn(c.get("title", str(c["_id"])), callback_data=f"cm_open_{c['_id']}")] for c in channels]
    rows.append([success_btn("➕ Add Channel", callback_data="cm_addchannel")])
    rows.append([danger_btn("✖️ Close", callback_data="go_close")])
    text = "📡 **Your Connected Channels**\n\nTap a channel to manage it, or add a new one." if channels else (
        "😕 You have no connected channels yet.\n\nTap **Add Channel** below to connect one."
    )
    return text, InlineKeyboardMarkup(rows)


async def render_channel(chat_id: int):
    ch = await db.get_channel(chat_id)
    if not ch:
        return None, None
    auto = ch.get("auto_caption", True)
    rev = ch.get("caption_reversal", False)
    md = ch.get("media_details", False)
    tmdb = ch.get("use_tmdb", True)
    text = (
        f"⚙️ **Channel Settings Panel**\n\n"
        f"📌 **Title:** {ch.get('title')}\n"
        f"🆔 **Channel ID:** `{chat_id}`\n\n"
        f"Use the buttons below to customize auto-captioning for this channel."
    )
    markup = InlineKeyboardMarkup(
        [
            [plain_btn("Auto Caption", callback_data="cm_noop"),
             (success_btn if auto else danger_btn)("ON ✅" if auto else "OFF ❌", callback_data=f"cm_toggle_auto_{chat_id}")],
            [plain_btn("Caption Reversal", callback_data="cm_noop"),
             (success_btn if rev else danger_btn)("Enabled ✅" if rev else "Disabled ❌", callback_data=f"cm_toggle_rev_{chat_id}")],
            [plain_btn("Media Details", callback_data="cm_noop"),
             (success_btn if md else danger_btn)("Enabled ✅" if md else "Disabled ❌", callback_data=f"cm_toggle_md_{chat_id}")],
            [plain_btn("TMDB Title Lookup", callback_data="cm_noop"),
             (success_btn if tmdb else danger_btn)("ON ✅" if tmdb else "OFF ❌", callback_data=f"cm_toggle_tmdb_{chat_id}")],
            [primary_btn("✏️ Caption", callback_data=f"cm_caption_{chat_id}"),
             primary_btn("🔘 Button", callback_data=f"cm_button_{chat_id}")],
            [primary_btn("✨ Prefix", callback_data=f"cm_prefix_{chat_id}"),
             primary_btn("✨ Suffix", callback_data=f"cm_suffix_{chat_id}")],
            [primary_btn("🔤 Words", callback_data=f"cm_words_{chat_id}")],
            [danger_btn("❌ Remove Channel", callback_data=f"cm_removeconfirm_{chat_id}")],
            [plain_btn("🔙 Back", callback_data="cm_list")],
        ]
    )
    return text, markup


async def render_caption_menu(chat_id: int):
    current = await db.get_caption_raw(chat_id)
    current_line = f"📋 **Current template:**\n`{current}`" if current else "❌ You haven't added any caption yet."
    text = CAPTION_GUIDE + "\n\n" + current_line
    markup = InlineKeyboardMarkup(
        [
            [success_btn("➕ Add Caption", callback_data=f"cm_addcap_{chat_id}")],
            [danger_btn("♻️ Reset Caption", callback_data=f"cm_resetcap_{chat_id}")],
            [primary_btn("🎨 Caption Font", callback_data=f"cm_font_{chat_id}")],
            [plain_btn("🔙 Back to Channel", callback_data=f"cm_open_{chat_id}")],
        ]
    )
    return text, markup


async def render_font_menu(chat_id: int):
    ch = await db.get_channel(chat_id)
    current = (ch or {}).get("caption_font", "normal")
    rows = []
    for key, label in FONT_OPTIONS:
        mark = " ✓" if key == current else ""
        rows.append([(success_btn if key == current else plain_btn)(label + mark, callback_data=f"cm_setfont_{chat_id}_{key}")])
    rows.append([plain_btn("🔙 Back", callback_data=f"cm_caption_{chat_id}")])
    return "🎨 **Choose a caption font style:**", InlineKeyboardMarkup(rows)


async def render_button_menu(chat_id: int):
    ch = await db.get_channel(chat_id)
    current = (ch or {}).get("custom_buttons")
    current_line = f"📋 **Current:**\n`{current}`" if current else "❌ No custom button set yet."
    text = BUTTON_GUIDE + "\n\n" + current_line
    markup = InlineKeyboardMarkup(
        [
            [success_btn("➕ Add Button", callback_data=f"cm_addbtn_{chat_id}")],
            [danger_btn("🗑 Remove Button", callback_data=f"cm_delbtn_{chat_id}")],
            [plain_btn("🔙 Back to Channel", callback_data=f"cm_open_{chat_id}")],
        ]
    )
    return text, markup


async def render_words_menu(chat_id: int):
    ch = await db.get_channel(chat_id)
    removes = (ch or {}).get("remove_words", [])
    replaces = (ch or {}).get("replace_words", {})
    lines = [WORDS_GUIDE, ""]
    lines.append(f"🧹 **Remove list ({len(removes)}):** " + (", ".join(f"`{w}`" for w in removes) if removes else "empty"))
    if replaces:
        lines.append("♻️ **Replace list:** " + ", ".join(f"`{k}`→`{v}`" for k, v in replaces.items()))
    else:
        lines.append("♻️ **Replace list:** empty")
    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(
        [
            [success_btn("🧹 Remove Text", callback_data=f"cm_addremove_{chat_id}"),
             success_btn("♻️ Replace Text", callback_data=f"cm_addreplace_{chat_id}")],
            [danger_btn("🗑 Clear All", callback_data=f"cm_clearwords_{chat_id}")],
            [plain_btn("🔙 Back to Channel", callback_data=f"cm_open_{chat_id}")],
        ]
    )
    return text, markup


async def render_prefix_menu(chat_id: int):
    ch = await db.get_channel(chat_id)
    current = (ch or {}).get("prefix", "")
    current_line = f"📋 **Current prefix:**\n`{current}`" if current else "❌ No prefix set."
    text = "✨ **Prefix** — text added to the *top* of every caption.\n\n" + current_line
    markup = InlineKeyboardMarkup(
        [
            [success_btn("➕ Set Prefix", callback_data=f"cm_setprefix_{chat_id}")],
            [danger_btn("🗑 Remove Prefix", callback_data=f"cm_delprefix_{chat_id}")],
            [plain_btn("🔙 Back to Channel", callback_data=f"cm_open_{chat_id}")],
        ]
    )
    return text, markup


async def render_suffix_menu(chat_id: int):
    ch = await db.get_channel(chat_id)
    current = (ch or {}).get("suffix", "")
    current_line = f"📋 **Current suffix:**\n`{current}`" if current else "❌ No suffix set."
    text = "✨ **Suffix** — text added to the *bottom* of every caption.\n\n" + current_line
    markup = InlineKeyboardMarkup(
        [
            [success_btn("➕ Set Suffix", callback_data=f"cm_setsuffix_{chat_id}")],
            [danger_btn("🗑 Remove Suffix", callback_data=f"cm_delsuffix_{chat_id}")],
            [plain_btn("🔙 Back to Channel", callback_data=f"cm_open_{chat_id}")],
        ]
    )
    return text, markup


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(app: Client):
    @app.on_message(filters.command(["channels", "mychannels"]) & filters.private)
    async def channels_cmd(client: Client, message: Message):
        text, markup = await render_list(message.from_user.id)
        await message.reply_text(text, reply_markup=markup)

    @app.on_callback_query(filters.regex("^cm_list$"))
    async def cb_list(client: Client, cq: CallbackQuery):
        clear_wait(cq.from_user.id)
        text, markup = await render_list(cq.from_user.id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex("^cm_noop$"))
    async def cb_noop(client: Client, cq: CallbackQuery):
        await cq.answer()

    @app.on_callback_query(filters.regex("^cm_addchannel$"))
    async def cb_addchannel(client: Client, cq: CallbackQuery):
        set_wait(cq.from_user.id, "cm_add_channel")
        text = (
            "📡 **Connect a new channel**\n\n"
            "Forward **any message from that channel** to me here (or forward it from the channel's discussion group).\n\n"
            "Before you do, please make sure:\n"
            "• I'm already an **admin** in that channel\n"
            "• **You** are also an **admin** in that channel\n\n"
            "Waiting for your forwarded message..."
        )
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data="cm_list")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_open_(-?\d+)$"))
    async def cb_open(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            await cq.answer("You can't manage this channel.", show_alert=True)
            return
        clear_wait(cq.from_user.id)
        text, markup = await render_channel(chat_id)
        if not text:
            await cq.answer("Channel not found.", show_alert=True)
            return
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_toggle_auto_(-?\d+)$"))
    async def cb_toggle_auto(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        ch = await db.get_channel(chat_id)
        await db.toggle_auto_caption(chat_id, not ch.get("auto_caption", True))
        text, markup = await render_channel(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_toggle_rev_(-?\d+)$"))
    async def cb_toggle_rev(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        ch = await db.get_channel(chat_id)
        await db.toggle_caption_reversal(chat_id, not ch.get("caption_reversal", False))
        text, markup = await render_channel(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_toggle_md_(-?\d+)$"))
    async def cb_toggle_md(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        ch = await db.get_channel(chat_id)
        await db.toggle_media_details(chat_id, not ch.get("media_details", False))
        text, markup = await render_channel(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_toggle_tmdb_(-?\d+)$"))
    async def cb_toggle_tmdb(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        ch = await db.get_channel(chat_id)
        await db.toggle_use_tmdb(chat_id, not ch.get("use_tmdb", True))
        text, markup = await render_channel(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_caption_(-?\d+)$"))
    async def cb_caption(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        clear_wait(cq.from_user.id)
        text, markup = await render_caption_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_addcap_(-?\d+)$"))
    async def cb_addcap(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        set_wait(cq.from_user.id, "cm_set_caption", chat_id=chat_id)
        text = "✏️ Send your new caption template as a message now."
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_caption_{chat_id}")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_resetcap_(-?\d+)$"))
    async def cb_resetcap(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.set_caption(chat_id, None)
        await cq.answer("Caption reset.", show_alert=True)
        text, markup = await render_caption_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_font_(-?\d+)$"))
    async def cb_font(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        text, markup = await render_font_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_setfont_(-?\d+)_(\w+)$"))
    async def cb_setfont(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        font = cq.matches[0].group(2)
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.set_caption_font(chat_id, font)
        await cq.answer(f"Font set to {font}.")
        text, markup = await render_font_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_button_(-?\d+)$"))
    async def cb_button_menu(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        clear_wait(cq.from_user.id)
        text, markup = await render_button_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_addbtn_(-?\d+)$"))
    async def cb_addbtn(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        set_wait(cq.from_user.id, "cm_set_button", chat_id=chat_id)
        text = "🔘 Send your button template now, e.g.\n`[Rkn Developer][buttonurl:https://t.me/RknDeveloper]`"
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_button_{chat_id}")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_delbtn_(-?\d+)$"))
    async def cb_delbtn(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.set_custom_buttons(chat_id, None)
        await cq.answer("Button removed.", show_alert=True)
        text, markup = await render_button_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_words_(-?\d+)$"))
    async def cb_words(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        clear_wait(cq.from_user.id)
        text, markup = await render_words_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_addremove_(-?\d+)$"))
    async def cb_addremove(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        set_wait(cq.from_user.id, "cm_remove_word", chat_id=chat_id)
        text = "🧹 Send the word or phrase to remove from captions."
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_words_{chat_id}")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_addreplace_(-?\d+)$"))
    async def cb_addreplace(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        set_wait(cq.from_user.id, "cm_replace_word_old", chat_id=chat_id)
        text = "♻️ Send the word/phrase you want to **replace**."
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_words_{chat_id}")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_clearwords_(-?\d+)$"))
    async def cb_clearwords(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.clear_remove_words(chat_id)
        await db.clear_replace_words(chat_id)
        await cq.answer("Cleared.", show_alert=True)
        text, markup = await render_words_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_prefix_(-?\d+)$"))
    async def cb_prefix(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        clear_wait(cq.from_user.id)
        text, markup = await render_prefix_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_setprefix_(-?\d+)$"))
    async def cb_setprefix(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        set_wait(cq.from_user.id, "cm_set_prefix", chat_id=chat_id)
        text = "✨ Send the text to use as prefix."
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_prefix_{chat_id}")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_delprefix_(-?\d+)$"))
    async def cb_delprefix(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.set_prefix(chat_id, "")
        await cq.answer("Prefix removed.", show_alert=True)
        text, markup = await render_prefix_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_suffix_(-?\d+)$"))
    async def cb_suffix(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        clear_wait(cq.from_user.id)
        text, markup = await render_suffix_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_setsuffix_(-?\d+)$"))
    async def cb_setsuffix(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        set_wait(cq.from_user.id, "cm_set_suffix", chat_id=chat_id)
        text = "✨ Send the text to use as suffix."
        markup = InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_suffix_{chat_id}")]])
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_delsuffix_(-?\d+)$"))
    async def cb_delsuffix(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.set_suffix(chat_id, "")
        await cq.answer("Suffix removed.", show_alert=True)
        text, markup = await render_suffix_menu(chat_id)
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_removeconfirm_(-?\d+)$"))
    async def cb_removeconfirm(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        ch = await db.get_channel(chat_id)
        text = f"⚠️ Disconnect **{ch.get('title')}**? This cannot be undone."
        markup = InlineKeyboardMarkup(
            [
                [danger_btn("✅ Yes, Remove", callback_data=f"cm_removeyes_{chat_id}"),
                 plain_btn("❌ No, Cancel", callback_data=f"cm_open_{chat_id}")]
            ]
        )
        await safe_edit(cq, text, markup)

    @app.on_callback_query(filters.regex(r"^cm_removeyes_(-?\d+)$"))
    async def cb_removeyes(client: Client, cq: CallbackQuery):
        chat_id = int(cq.matches[0].group(1))
        if not await _can_manage(cq.from_user.id, chat_id):
            return await cq.answer("Not allowed.", show_alert=True)
        await db.remove_channel(chat_id)
        await cq.answer("Channel removed.", show_alert=True)
        text, markup = await render_list(cq.from_user.id)
        await safe_edit(cq, text, markup)

    @app.on_message(filters.private & filters.incoming, group=2)
    async def waiting_input_handler(client: Client, message: Message):
        state = get_wait(message.from_user.id)
        if not state:
            return
        action = state["action"]

        if message.text and message.text.startswith("/"):
            return

        if action == "cm_add_channel":
            fwd_chat = None
            if getattr(message, "forward_origin", None):
                if hasattr(message.forward_origin, "chat"):
                    fwd_chat = message.forward_origin.chat
                elif hasattr(message.forward_origin, "sender_chat"):
                    fwd_chat = message.forward_origin.sender_chat
            
            if not fwd_chat:
                fwd_chat = getattr(message, "forward_from_chat", None)

            if not fwd_chat or fwd_chat.type != ChatType.CHANNEL:
                await message.reply_text(
                    "⚠️ That's not a forwarded channel post. Please forward a message "
                    "directly from the channel you want to connect.",
                )
                return

            bot_id = getattr(client, "bot_id", None)
            try:
                bot_member = await client.get_chat_member(fwd_chat.id, bot_id or (await client.get_me()).id)
                bot_is_admin = bot_member.status in (
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.OWNER,
                )
            except Exception:
                bot_is_admin = False

            if not bot_is_admin:
                await message.reply_text(
                    f"❌ I'm not an admin in **{fwd_chat.title}** yet.\n\n"
                    "Please add me as admin there first, then forward the message again.",
                    reply_markup=InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data="cm_list")]]),
                )
                return

            if not is_sudo(message.from_user.id):
                try:
                    user_member = await client.get_chat_member(fwd_chat.id, message.from_user.id)
                    user_is_admin = user_member.status in (
                        ChatMemberStatus.ADMINISTRATOR,
                        ChatMemberStatus.OWNER,
                    )
                except Exception:
                    user_is_admin = False
                if not user_is_admin:
                    await message.reply_text(
                        f"❌ You're not an admin in **{fwd_chat.title}**, so you can't connect it.",
                        reply_markup=InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data="cm_list")]]),
                    )
                    return

            await db.add_channel(fwd_chat.id, fwd_chat.title or "Unknown", message.from_user.id)
            clear_wait(message.from_user.id)
            text, markup = await render_channel(fwd_chat.id)
            final_text = f"✅ **{fwd_chat.title} connected!**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)
            return

        chat_id = state.get("chat_id")

        if action == "cm_set_caption" and message.text:
            await db.set_caption(chat_id, message.text)
            clear_wait(message.from_user.id)
            text, markup = await render_caption_menu(chat_id)
            final_text = f"✅ **Caption template updated.**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)

        elif action == "cm_set_button" and message.text:
            await db.set_custom_buttons(chat_id, message.text)
            clear_wait(message.from_user.id)
            text, markup = await render_button_menu(chat_id)
            final_text = f"✅ **Button saved.**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)

        elif action == "cm_remove_word" and message.text:
            await db.add_remove_word(chat_id, message.text.strip())
            clear_wait(message.from_user.id)
            text, markup = await render_words_menu(chat_id)
            final_text = f"✅ **Added to remove list.**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)

        elif action == "cm_replace_word_old" and message.text:
            set_wait(message.from_user.id, "cm_replace_word_new", chat_id=chat_id, old=message.text.strip())
            await message.reply_text(
                "♻️ Now send the **replacement** text.",
                reply_markup=InlineKeyboardMarkup([[danger_btn("❌ Cancel", callback_data=f"cm_words_{chat_id}")]]),
            )

        elif action == "cm_replace_word_new" and message.text:
            await db.add_replace_word(chat_id, state.get("old", ""), message.text.strip())
            clear_wait(message.from_user.id)
            text, markup = await render_words_menu(chat_id)
            final_text = f"✅ **Added to replace list.**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)

        elif action == "cm_set_prefix" and message.text:
            await db.set_prefix(chat_id, message.text)
            clear_wait(message.from_user.id)
            text, markup = await render_prefix_menu(chat_id)
            final_text = f"✅ **Prefix saved.**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)

        elif action == "cm_set_suffix" and message.text:
            await db.set_suffix(chat_id, message.text)
            clear_wait(message.from_user.id)
            text, markup = await render_suffix_menu(chat_id)
            final_text = f"✅ **Suffix saved.**\n\n{text}"
            await message.reply_text(final_text, reply_markup=markup)
