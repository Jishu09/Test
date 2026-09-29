import asyncio
import os
import time

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import delete_all
from config import Config
from main import SUBTITLE_EXTENSIONS, VIDEO_EXTENSIONS, formatDB, queueDB
from Vivian.Function.ffmpeg import HardSubVideo
from Vivian.Tools.display_progress import Progress


def is_auth(message: Message) -> bool:
    return message.chat.id == int(Config.OWNER)


@Client.on_message(filters.incoming & filters.command(["hsub"]))
async def hsub_cmd_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply_text("Please reply to a video message with /hsub to hardsub it using its soft subtitle.")

    media = message.reply_to_message.video or message.reply_to_message.document
    if not media.file_name:
        return await message.reply_text("File name not found")

    status_msg = await message.reply_text("📥 Downloading video...", quote=True)
    prog = Progress(message.from_user.id, app, status_msg)

    download_dir = f"downloads/{message.from_user.id}/"
    os.makedirs(download_dir, exist_ok=True)

    try:
        download_path = await app.download_media(
            message=message.reply_to_message,
            file_name=f"{download_dir}{media.file_name}",
            progress=prog.progress_for_pyrogram,
            progress_args=("Downloading...", time.time())
        )
    except Exception as e:
        return await status_msg.edit_text(f"❌ Failed to download video: {e}")

    if not download_path:
        return await status_msg.edit_text("❌ Download cancelled or failed.")

    await status_msg.edit_text("⚙️ Hardsubbing video (using internal subs)...")

    output_file = os.path.join(download_dir, "hardsubbed.mkv")

    success = await HardSubVideo(download_path, download_path, output_file)

    if not success or not os.path.exists(output_file):
        if os.path.exists(download_path):
            os.remove(download_path)
        return await status_msg.edit_text("❌ Hardsub failed. (Does it have soft subs?)")

    await status_msg.edit_text("📤 Uploading video...")

    upload_prog = Progress(message.from_user.id, app, status_msg)

    try:
        await app.send_document(
            chat_id=message.chat.id,
            document=output_file,
            caption="Here is your hardsubbed video! 🎥",
            progress=upload_prog.progress_for_pyrogram,
            progress_args=("Uploading...", time.time())
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to upload video: {e}")

    finally:
        await delete_all(root=download_dir)


@Client.on_message(filters.incoming & filters.command(["ssub"]))
async def ssub_cmd_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply_text("Please reply to a video message with /ssub to add a soft subtitle.")

    video_msg = message.reply_to_message
    media = video_msg.video or video_msg.document
    if not media.file_name:
        return await message.reply_text("File name not found")

    ext = media.file_name.split('.')[-1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return await message.reply_text("Replied file must be a video.")

    await message.reply_text("Send me the subtitle file you want to add.")

    try:
        sub_msg = await app.listen(chat_id=message.chat.id, timeout=300)
    except asyncio.TimeoutError:
        return await message.reply_text("Timeout waiting for subtitle.")

    if not sub_msg or not sub_msg.document:
        return await message.reply_text("Invalid subtitle file provided.")

    sub_media = sub_msg.document
    if not sub_media.file_name:
        return await message.reply_text("Subtitle file name not found.")

    sub_ext = sub_media.file_name.split('.')[-1].lower()
    if sub_ext not in SUBTITLE_EXTENSIONS:
        return await message.reply_text("Please send a valid subtitle file (e.g. srt, ass).")

    user_id = message.from_user.id

    queueDB.update(
        {user_id: {"videos": [video_msg.id], "subtitles": [sub_msg.id], "audios": []}})
    formatDB.update({user_id: ext})

    await message.reply_text(
        text="Do you want to rename hardsub? Default file name is **[@yashoswalyo]_merged.mkv**",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("👆 Default", callback_data="rename_hardsub_NO"),
                    InlineKeyboardButton("✍️ Rename", callback_data="rename_hardsub_YES"),
                ],
                [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
            ]
        ),
        quote=True,
    )
