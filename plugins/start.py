import os
import time
import random

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import (
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
    InputMediaPhoto,
)

from bot.config import Config
from bot.database import db
from utils.buttons import primary_btn, success_btn, danger_btn, plain_btn
from utils.helpers import uptime, is_sudo
from plugins.script import START_TEXT, HELP_TEXT, ABOUT_TEXT, OWNER_HELP_TEXT

# SafeDict prevents the bot from crashing if an unknown format (like {unknown}) is used in script.py
class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def get_start_pics():
    pics_str = os.environ.get("START_PICS", "")
    if pics_str:
        return [pic.strip() for pic in pics_str.split(",") if pic.strip()]
    return []


def home_markup():
    rows = [
        [success_btn("📡 My Channels", callback_data="cm_list")],
        [success_btn("📖 Help", callback_data="go_help"), primary_btn("ℹ️ About", callback_data="go_about")],
    ]
    if Config.SUPPORT_CHAT:
        rows.append([plain_btn("💬 Support", url=Config.SUPPORT_CHAT)])
    rows.append([danger_btn("✖️ Close", callback_data="go_close")])
    return InlineKeyboardMarkup(rows)


def help_markup(user_id: int):
    rows = []
    # Check if the user is the owner, if yes, show the owner commands button
    if user_id == Config.OWNER_ID:
        rows.append([primary_btn("🛠 Owner Commands", callback_data="go_owner_help")])
    rows.append([primary_btn("🔙 Back", callback_data="go_home")])
    return InlineKeyboardMarkup(rows)


def back_markup():
    return InlineKeyboardMarkup([[primary_btn("🔙 Back", callback_data="go_home")]])


def register(app: Client):
    @app.on_message(filters.command("start") & filters.private)
    async def start_cmd(client: Client, message: Message):
        from plugins.fsub import force_sub_guard
        if not await force_sub_guard(client, message):
            return

        user = message.from_user
        await db.add_user(
            user.id,
            user.first_name or "",
            user.username or "",
        )
        
        # Format variables safely mapping all details
        format_data = SafeDict(
            first=user.first_name or "User",
            last=user.last_name or "",
            fullname=f"{user.first_name or ''} {user.last_name or ''}".strip() or "User",
            username=user.username or "",
            mention=user.mention,
            id=user.id,
            bot_name=Config.BOT_NAME
        )
        text = START_TEXT.format_map(format_data)
        
        pics = get_start_pics()
        if pics:
            pic = random.choice(pics)
            await message.reply_photo(
                photo=pic,
                caption=text,
                reply_markup=home_markup(),
            )
        else:
            await message.reply_text(text, reply_markup=home_markup())

    @app.on_message(filters.command("help") & filters.private)
    async def help_cmd(client: Client, message: Message):
        await message.reply_text(HELP_TEXT, reply_markup=help_markup(message.from_user.id))

    @app.on_message(filters.command("about"))
    async def about_cmd(client: Client, message: Message):
        await message.reply_text(
            ABOUT_TEXT.format(bot_name=Config.BOT_NAME),
            reply_markup=back_markup(),
        )

    @app.on_message(filters.command("ping"))
    async def ping_cmd(client: Client, message: Message):
        start = time.time()
        m = await message.reply_text("🏓 Pinging...")
        delta = (time.time() - start) * 1000
        await m.edit_text(f"🏓 **Pong!** `{delta:.2f} ms`\n⏱ Uptime: `{uptime()}`")

    @app.on_callback_query(filters.regex("^go_help$"))
    async def cb_help(client: Client, cq: CallbackQuery):
        is_media = bool(cq.message.photo or cq.message.video or cq.message.animation)
        markup = help_markup(cq.from_user.id)
        
        if is_media:
            await cq.message.edit_caption(caption=HELP_TEXT, reply_markup=markup)
        else:
            await cq.message.edit_text(text=HELP_TEXT, reply_markup=markup)

    @app.on_callback_query(filters.regex("^go_owner_help$"))
    async def cb_owner_help(client: Client, cq: CallbackQuery):
        # Double-check security: if non-owner somehow triggers this, reject them
        if cq.from_user.id != Config.OWNER_ID:
            return await cq.answer("❌ You don't have permission to view this.", show_alert=True)
            
        markup = InlineKeyboardMarkup([[primary_btn("🔙 Back", callback_data="go_help")]])
        is_media = bool(cq.message.photo or cq.message.video or cq.message.animation)
        
        if is_media:
            await cq.message.edit_caption(caption=OWNER_HELP_TEXT, reply_markup=markup)
        else:
            await cq.message.edit_text(text=OWNER_HELP_TEXT, reply_markup=markup)

    @app.on_callback_query(filters.regex("^go_about$"))
    async def cb_about(client: Client, cq: CallbackQuery):
        text = ABOUT_TEXT.format(bot_name=Config.BOT_NAME)
        is_media = bool(cq.message.photo or cq.message.video or cq.message.animation)
        
        if is_media:
            await cq.message.edit_caption(caption=text, reply_markup=back_markup())
        else:
            await cq.message.edit_text(text=text, reply_markup=back_markup())

    @app.on_callback_query(filters.regex("^go_home$"))
    async def cb_home(client: Client, cq: CallbackQuery):
        user = cq.from_user
        format_data = SafeDict(
            first=user.first_name or "User",
            last=user.last_name or "",
            fullname=f"{user.first_name or ''} {user.last_name or ''}".strip() or "User",
            username=user.username or "",
            mention=user.mention,
            id=user.id,
            bot_name=Config.BOT_NAME
        )
        text = START_TEXT.format_map(format_data)
        is_media = bool(cq.message.photo or cq.message.video or cq.message.animation)
        
        if is_media:
            await cq.message.edit_caption(caption=text, reply_markup=home_markup())
        else:
            await cq.message.edit_text(text=text, reply_markup=home_markup())

    @app.on_callback_query(filters.regex("^go_close$"))
    async def cb_close(client: Client, cq: CallbackQuery):
        try:
            await cq.message.delete()
        except Exception:
            # Bot can't always delete its own message in every context
            # (Telegram returns MESSAGE_DELETE_FORBIDDEN in some setups) —
            # fall back to just clearing the buttons instead of crashing.
            try:
                if cq.message.photo or cq.message.video or cq.message.animation:
                    await cq.message.edit_caption(caption="✖️ Closed.")
                else:
                    await cq.message.edit_text("✖️ Closed.")
            except Exception:
                pass

    @app.on_chat_member_updated()
    async def on_promoted(client: Client, event: ChatMemberUpdated):
        if event.new_chat_member is None:
            return
        # Cached once at startup (main.py) — calling get_me() here on every
        # single member-update event (which fires for ALL users joining/
        # leaving/being promoted in every chat the bot is in, not just the
        # bot itself) was hammering the API and triggering FLOOD_WAIT.
        bot_id = getattr(client, "bot_id", None)
        if bot_id is None:
            return  # startup race — bot_id not cached yet, skip safely
        if event.new_chat_member.user.id != bot_id:
            return
        if event.chat.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP):
            return
        if event.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
            created = await db.add_channel(
                event.chat.id,
                event.chat.title or "Unknown",
                event.from_user.id if event.from_user else 0,
            )
            if created and Config.LOG_CHANNEL:
                try:
                    await client.send_message(
                        Config.LOG_CHANNEL,
                        f"📡 **New Channel Connected**\n\n"
                        f"**Title:** {event.chat.title}\n"
                        f"**ID:** `{event.chat.id}`",
                    )
                except Exception:
                    pass
        elif event.new_chat_member.status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.BANNED,
        ):
            await db.remove_channel(event.chat.id)
