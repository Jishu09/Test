import asyncio

from pyrogram import Client, StopPropagation, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from main import VIDEO_EXTENSIONS, formatDB, queueDB


def is_auth(message: Message) -> bool:
    return message.chat.id == int(Config.OWNER)


@Client.on_message(filters.incoming & filters.command(["marge"]))
async def marge_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    user_id = message.from_user.id
    queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
    formatDB.update({user_id: None})

    await message.reply_text("Send videos to merge. Send /done when you are finished.")

    q = asyncio.Queue()

    async def _queue_handler(client, msg):
        if msg.chat.id == message.chat.id:
            await q.put(msg)
            raise StopPropagation

    handler = MessageHandler(
        _queue_handler, filters=filters.incoming & (
            filters.document | filters.video | filters.text))
    app.add_handler(handler, group=-1)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=300)
            except asyncio.TimeoutError:
                await message.reply_text("Timeout waiting for videos. Queue cleared.")
                queueDB.update(
                    {user_id: {"videos": [], "subtitles": [], "audios": []}})
                formatDB.update({user_id: None})
                break

            if msg.text and msg.text.startswith("/done"):
                break

            if msg.video or msg.document:
                media = msg.video or msg.document
                if media.file_name:
                    ext = media.file_name.split('.')[-1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        queueDB[user_id]["videos"].append(msg.id)
                        queueDB[user_id]["subtitles"].append(None)
                        if formatDB.get(user_id) is None:
                            formatDB.update({user_id: ext})
                        await message.reply_text(f"Added to queue. Total videos: {len(queueDB[user_id]['videos'])}")
                    else:
                        await message.reply_text("Only video files are supported for /marge")
                else:
                    await message.reply_text("Could not determine file extension.")
    finally:
        app.remove_handler(handler, group=-1)

    if not queueDB.get(user_id)["videos"]:
        await message.reply_text("No videos were added to the queue.")
        return

    await message.reply_text(
        text="Do you want to rename? Default file name is **[@yashoswalyo]_merged.mkv**",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("👆 Default", callback_data="rename_NO"),
                    InlineKeyboardButton("✍️ Rename", callback_data="rename_YES"),
                ],
                [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
            ]
        ),
        quote=True,
    )


@Client.on_message(filters.incoming & filters.command(["archive", "achieve"]))
async def archive_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    user_id = message.from_user.id
    queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
    formatDB.update({user_id: None})

    await message.reply_text("Send files to archive. Send /done when you are finished.")

    q = asyncio.Queue()

    async def _queue_handler(client, msg):
        if msg.chat.id == message.chat.id:
            await q.put(msg)
            raise StopPropagation

    handler = MessageHandler(_queue_handler, filters=filters.incoming & (
        filters.document | filters.video | filters.audio | filters.text))
    app.add_handler(handler, group=-1)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=300)
            except asyncio.TimeoutError:
                await message.reply_text("Timeout waiting for files. Queue cleared.")
                queueDB.update(
                    {user_id: {"videos": [], "subtitles": [], "audios": []}})
                formatDB.update({user_id: None})
                break

            if msg.text and msg.text.startswith("/done"):
                break

            if msg.video or msg.document or msg.audio:

                queueDB[user_id]["videos"].append(msg.id)
                await message.reply_text(f"Added to queue. Total files: {len(queueDB[user_id]['videos'])}")
    finally:
        app.remove_handler(handler, group=-1)

    if not queueDB.get(user_id)["videos"]:
        await message.reply_text("No files were added to the queue.")
        return

    await message.reply_text(
        text="Do you want to rename zip? Default file name is **[@yashoswalyo]_merged.zip**",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("👆 Default", callback_data="rename_zip_NO"),
                    InlineKeyboardButton("✍️ Rename", callback_data="rename_zip_YES"),
                ],
                [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
            ]
        ),
        quote=True,
    )
