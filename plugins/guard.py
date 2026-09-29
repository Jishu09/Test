from pyrogram import Client, filters
from pyrogram.types import Message

from bot.database import db
from utils.helpers import is_sudo


def register(app: Client):
    @app.on_message(filters.private & filters.incoming, group=-1)
    async def guard(client: Client, message: Message):
        if not message.from_user:
            return
        user_id = message.from_user.id

        if await db.is_banned(user_id):
            await message.reply_text("🚫 You are banned from using this bot.")
            message.stop_propagation()

        if await db.is_maintenance() and not is_sudo(user_id):
            await message.reply_text(
                "🛠 **Under Maintenance**\n\nThe bot is temporarily unavailable. Please try again later."
            )
            message.stop_propagation()
