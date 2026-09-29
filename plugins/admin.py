import os
import sys
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.config import Config
from bot.database import db
from utils.helpers import is_sudo, is_owner, uptime

START_TIME = time.time()


def register(app: Client):
    @app.on_message(filters.command("stats"))
    async def stats_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        users = await db.total_users_count()
        channels = await db.total_channels_count()
        fsub = len(await db.get_fsub_channels())
        try:
            dbstats = await db.db_stats()
            db_line = f"💾 DB Storage: `{dbstats['storage_mb']} MB` (`{dbstats['collections']}` collections)"
        except Exception:
            db_line = "💾 DB Storage: `N/A`"

        await message.reply_text(
            f"📊 **Bot Statistics**\n\n"
            f"👥 Users: `{users}`\n"
            f"📡 Connected Channels: `{channels}`\n"
            f"🔒 Force-Sub Channels: `{fsub}`\n"
            f"{db_line}\n"
            f"⏱ Uptime: `{uptime()}`",
        )

    @app.on_message(filters.command("ban"))
    async def ban_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/ban <user_id> [reason]`")
            return
        user_id = int(message.command[1])
        reason = message.text.split(None, 2)[2] if len(message.command) > 2 else "No reason given"
        await db.ban_user(user_id, reason)
        await message.reply_text(f"🚫 Banned `{user_id}`.\nReason: {reason}")

    @app.on_message(filters.command("unban"))
    async def unban_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/unban <user_id>`")
            return
        await db.unban_user(int(message.command[1]))
        await message.reply_text(f"✅ Unbanned `{message.command[1]}`.")

    @app.on_message(filters.command("maintenance"))
    async def maintenance_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if len(message.command) < 2 or message.command[1].lower() not in ("on", "off"):
            await message.reply_text("⚠️ Usage: `/maintenance on` or `/maintenance off`")
            return
        state = message.command[1].lower() == "on"
        await db.set_maintenance(state)
        await message.reply_text(f"🛠 Maintenance mode: **{'ON' if state else 'OFF'}**")

    @app.on_message(filters.command("restart"))
    async def restart_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        await message.reply_text("♻️ Restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)

    @app.on_message(filters.command("addsudo"))
    async def addsudo_cmd(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            await message.reply_text("⛔ Owner only command.")
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/addsudo <user_id>`")
            return
        uid = int(message.command[1])
        if uid not in Config.SUDO_USERS:
            Config.SUDO_USERS.append(uid)
        await message.reply_text(f"✅ `{uid}` added as sudo (until restart — update env vars to persist).")

    @app.on_message(filters.command("delsudo"))
    async def delsudo_cmd(client: Client, message: Message):
        if not is_owner(message.from_user.id):
            await message.reply_text("⛔ Owner only command.")
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/delsudo <user_id>`")
            return
        uid = int(message.command[1])
        if uid in Config.SUDO_USERS and uid != Config.OWNER_ID:
            Config.SUDO_USERS.remove(uid)
        await message.reply_text(f"✅ `{uid}` removed from sudo.")

    # ---------------- FORCE-SUB MANAGEMENT ----------------
    @app.on_message(filters.command("addfsub"))
    async def addfsub_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/addfsub <channel_id> [subscribe|request]`")
            return
        chat_id = int(message.command[1])
        mode = message.command[2].lower() if len(message.command) > 2 else "subscribe"
        if mode not in ("subscribe", "request"):
            mode = "subscribe"
        try:
            chat = await client.get_chat(chat_id)
            title = chat.title
        except Exception:
            title = str(chat_id)
        await db.add_fsub_channel(chat_id, mode)
        await message.reply_text(f"✅ Added **{title}** as force-sub ({mode} mode).")

    @app.on_message(filters.command("delfsub"))
    async def delfsub_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/delfsub <channel_id>`")
            return
        await db.remove_fsub_channel(int(message.command[1]))
        await message.reply_text("✅ Removed from force-sub list.")

    @app.on_message(filters.command("listfsub"))
    async def listfsub_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        channels = await db.get_fsub_channels()
        if not channels:
            await message.reply_text("📭 No force-sub channels configured.")
            return
        lines = []
        for ch in channels:
            try:
                chat = await client.get_chat(ch["_id"])
                title = chat.title
            except Exception:
                title = str(ch["_id"])
            lines.append(f"• {title} — `{ch['_id']}` (`{ch.get('mode', 'subscribe')}`)")
        await message.reply_text("🔒 **Force-Sub Channels:**\n\n" + "\n".join(lines))
