import asyncio
import time

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from bot.database import db
from utils.helpers import is_sudo


def register(app: Client):
    @app.on_message(filters.command("broadcast") & filters.private)
    async def broadcast_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if not message.reply_to_message:
            await message.reply_text("⚠️ Reply to a message with `/broadcast` to send it to all users.")
            return

        target = message.reply_to_message
        users = [u async for u in await db.get_all_users()]
        total = len(users)
        status = await message.reply_text(f"📣 Broadcasting to **{total}** users...")

        sent, failed, blocked = 0, 0, 0
        start = time.time()
        for user in users:
            try:
                await target.copy(user["_id"])
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await target.copy(user["_id"])
                    sent += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1
                blocked += 1
                await db.delete_user(user["_id"])
            await asyncio.sleep(0.05)

        elapsed = round(time.time() - start, 1)
        await status.edit_text(
            f"✅ **Broadcast complete** in `{elapsed}s`\n\n"
            f"👥 Total: `{total}`\n"
            f"✔️ Sent: `{sent}`\n"
            f"❌ Failed/Blocked: `{failed}` (removed from DB: `{blocked}`)"
        )

    @app.on_message(filters.command("cbroadcast") & filters.private)
    async def channel_broadcast_cmd(client: Client, message: Message):
        if not is_sudo(message.from_user.id):
            return
        if not message.reply_to_message:
            await message.reply_text(
                "⚠️ Reply to a message with `/cbroadcast` to post it to all connected channels.",
            )
            return

        target = message.reply_to_message
        channels = [c async for c in await db.get_all_channels()]
        total = len(channels)
        status = await message.reply_text(f"📣 Posting to **{total}** channels...")

        sent, failed = 0, 0
        for ch in channels:
            try:
                await target.copy(ch["_id"])
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await target.copy(ch["_id"])
                    sent += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.1)

        await status.edit_text(
            f"✅ **Channel broadcast complete**\n\n"
            f"📡 Total: `{total}`\n✔️ Sent: `{sent}`\n❌ Failed: `{failed}`"
        )
