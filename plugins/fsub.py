import os
import time
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import ChatJoinRequest, InlineKeyboardMarkup, InputMediaPhoto

from bot.database import db
from bot.config import Config
from utils.buttons import primary_btn, success_btn

FSUB_TEXT = (
    "🔒 **Access Restricted**\n\n"
    "Please join the channel(s) below to use this bot, then tap **Try Again**."
)


def get_fsub_pics():
    pics_str = os.environ.get("FSUB_PICS", "") or os.environ.get("START_PICS", "")
    if pics_str:
        return [pic.strip() for pic in pics_str.split(",") if pic.strip()]
    return []


async def get_missing_channels(client: Client, user_id: int) -> list:
    """Return list of fsub channel docs the user hasn't joined/requested yet."""
    channels = await db.get_fsub_channels()
    missing = []
    
    for ch in channels:
        chat_id = ch["_id"]
        mode = ch.get("mode", "subscribe")
        
        is_member = False
        try:
            member = await client.get_chat_member(chat_id, user_id)
            if member.status not in (
                ChatMemberStatus.BANNED,
                ChatMemberStatus.LEFT,
            ):
                is_member = True
        except UserNotParticipant:
            is_member = False
        except Exception:
            is_member = True
            
        if mode == "request":
            if not is_member:
                if not await db.has_join_request(chat_id, user_id):
                    missing.append(ch)
        else:
            if not is_member:
                missing.append(ch)
                
    return missing


async def build_fsub_markup(client: Client, missing: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in missing:
        chat_id = ch["_id"]
        try:
            chat = await client.get_chat(chat_id)
            title = chat.title or "Channel"
            if ch.get("mode") == "request":
                link = chat.invite_link or await client.create_chat_invite_link(
                    chat_id, creates_join_request=True
                )
                url = link if isinstance(link, str) else link.invite_link
            else:
                url = chat.invite_link or (
                    await client.export_chat_invite_link(chat_id)
                )
        except Exception:
            continue
        rows.append([primary_btn(f"Join {title}", url=url)])
    rows.append([success_btn("🔄 Try Again", callback_data="fsub_recheck")])
    return InlineKeyboardMarkup(rows)


async def force_sub_guard(client: Client, message) -> bool:
    """Returns True if user passed fsub (or none configured). Sends prompt otherwise."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return True
        
    from utils.helpers import is_sudo
    if is_sudo(user_id):
        return True
        
    missing = await get_missing_channels(client, user_id)
    if not missing:
        return True
        
    markup = await build_fsub_markup(client, missing)
    pics = get_fsub_pics()
    
    if pics:
        pic = random.choice(pics)
        await message.reply_photo(
            photo=pic,
            caption=FSUB_TEXT,
            reply_markup=markup,
        )
    else:
        await message.reply_text(FSUB_TEXT, reply_markup=markup)
    return False


def register(app: Client):
    @app.on_chat_join_request(filters.all)
    async def on_join_request(client: Client, request: ChatJoinRequest):
        chat = request.chat
        user = request.from_user
        ch_doc = None
        for c in await db.get_fsub_channels():
            if c["_id"] == chat.id:
                ch_doc = c
                break
        if not ch_doc or ch_doc.get("mode") != "request":
            return
            
        await db.record_join_request(chat.id, user.id)
        try:
            await client.approve_chat_join_request(chat.id, user.id)
        except Exception:
            pass

    @app.on_callback_query(filters.regex("^fsub_recheck$"))
    async def recheck(client: Client, cq):
        missing = await get_missing_channels(client, cq.from_user.id)
        if not missing:
            from plugins.start import START_TEXT, home_markup, get_start_pics, SafeDict

            user = cq.from_user
            format_data = SafeDict(
                first=user.first_name or "User",
                last=user.last_name or "",
                fullname=f"{user.first_name or ''} {user.last_name or ''}".strip() or "User",
                username=user.username or "",
                mention=user.mention,
                id=user.id,
                bot_name=Config.BOT_NAME,
            )
            text = START_TEXT.format_map(format_data)
            pics = get_start_pics()
            
            if cq.message.photo or cq.message.video or cq.message.animation:
                if pics:
                    try:
                        pic = random.choice(pics)
                        await cq.edit_message_media(
                            media=InputMediaPhoto(pic, caption=text),
                            reply_markup=home_markup()
                        )
                    except Exception:
                        await cq.message.edit_caption(caption=text, reply_markup=home_markup())
                else:
                    await cq.message.edit_caption(caption=text, reply_markup=home_markup())
            else:
                await cq.message.edit_text(text=text, reply_markup=home_markup())
            return

        markup = await build_fsub_markup(client, missing)
        await cq.answer("You still haven't joined all required channels.", show_alert=True)
        try:
            await cq.message.edit_reply_markup(markup)
        except Exception:
            pass
