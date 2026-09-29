import os
import time

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram import Client, filters
from pyrogram.types import InputMediaPhoto, Message

from bot import delete_all
from config import Config
from main import LOGGER
from Vivian.Function.ffmpeg import cult_small_video, take_screen_shot
from Vivian.Tools.display_progress import Progress


def is_auth(message: Message) -> bool:
    return message.chat.id == int(Config.OWNER)


@Client.on_message(filters.incoming & filters.command(["ss"]))
async def ss_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply_text("Please reply to a video message with /ss")

    media = message.reply_to_message.video or message.reply_to_message.document

    status_msg = await message.reply_text("📥 Downloading video...", quote=True)
    prog = Progress(message.from_user.id, app, status_msg)

    download_dir = f"downloads/{message.from_user.id}/"
    os.makedirs(download_dir, exist_ok=True)

    try:
        download_path = await app.download_media(
            message=message.reply_to_message,
            file_name=f"{download_dir}{media.file_name or 'vid.mkv'}",
            progress=prog.progress_for_pyrogram,
            progress_args=("Downloading...", time.time())
        )
    except Exception as e:
        return await status_msg.edit_text(f"❌ Failed to download video: {e}")

    if not download_path:
        return await status_msg.edit_text("❌ Download cancelled or failed.")

    await status_msg.edit_text("⚙️ Generating screenshots...")

    duration = 0
    try:
        metadata = extractMetadata(createParser(download_path))
        if metadata.has("duration"):
            duration = metadata.get("duration").seconds
    except Exception as e:
        LOGGER.error(f"Failed to extract duration: {e}")

    if duration <= 0:
        duration = 60

    screenshots = []

    interval = max(duration // 11, 1)

    for i in range(1, 11):
        timestamp = i * interval
        ss_path = await take_screen_shot(download_path, download_dir, timestamp)
        if ss_path:
            screenshots.append(InputMediaPhoto(media=ss_path))

    if not screenshots:
        await status_msg.edit_text("❌ Failed to generate screenshots.")
        await delete_all(root=download_dir)
        return

    await status_msg.edit_text("📤 Uploading screenshots...")

    try:
        await app.send_media_group(
            chat_id=message.chat.id,
            media=screenshots,
            reply_to_message_id=message.reply_to_message.id
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to upload screenshots: {e}")
    finally:
        await delete_all(root=download_dir)


@Client.on_message(filters.incoming & filters.command(["simple"]))
async def simple_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply_text("Please reply to a video message with /simple")

    media = message.reply_to_message.video or message.reply_to_message.document

    status_msg = await message.reply_text("📥 Downloading video...", quote=True)
    prog = Progress(message.from_user.id, app, status_msg)

    download_dir = f"downloads/{message.from_user.id}/"
    os.makedirs(download_dir, exist_ok=True)

    try:
        download_path = await app.download_media(
            message=message.reply_to_message,
            file_name=f"{download_dir}{media.file_name or 'vid.mkv'}",
            progress=prog.progress_for_pyrogram,
            progress_args=("Downloading...", time.time())
        )
    except Exception as e:
        return await status_msg.edit_text(f"❌ Failed to download video: {e}")

    if not download_path:
        return await status_msg.edit_text("❌ Download cancelled or failed.")

    await status_msg.edit_text("⚙️ Creating simple 30sec video...")

    ext = download_path.split('.')[-1]

    out_path = await cult_small_video(download_path, download_dir, "00:00:00", "00:00:30", ext)

    if not out_path:
        await delete_all(root=download_dir)
        return await status_msg.edit_text("❌ Failed to create simple video.")

    await status_msg.edit_text("📤 Uploading simple video...")

    upload_prog = Progress(message.from_user.id, app, status_msg)

    try:
        await app.send_document(
            chat_id=message.chat.id,
            document=out_path,
            caption="Here is your 30s simple video! 🎥",
            progress=upload_prog.progress_for_pyrogram,
            progress_args=("Uploading...", time.time())
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to upload simple video: {e}")
    finally:
        await delete_all(root=download_dir)


@Client.on_message(filters.incoming & filters.command(["trim"]))
async def trim_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text("🚫 Admin Only")

    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply_text("Please reply to a video message with /trim start_time-end_time (e.g. /trim 00:02:00-00:04:00)")

    try:
        args = message.text.split(" ", maxsplit=1)[1]
        start_time, end_time = args.split("-")
    except Exception:
        return await message.reply_text("Usage: /trim start_time-end_time (e.g. /trim 00:02:00-00:04:00)")

    media = message.reply_to_message.video or message.reply_to_message.document

    status_msg = await message.reply_text("📥 Downloading video...", quote=True)
    prog = Progress(message.from_user.id, app, status_msg)

    download_dir = f"downloads/{message.from_user.id}/"
    os.makedirs(download_dir, exist_ok=True)

    try:
        download_path = await app.download_media(
            message=message.reply_to_message,
            file_name=f"{download_dir}{media.file_name or 'vid.mkv'}",
            progress=prog.progress_for_pyrogram,
            progress_args=("Downloading...", time.time())
        )
    except Exception as e:
        return await status_msg.edit_text(f"❌ Failed to download video: {e}")

    if not download_path:
        return await status_msg.edit_text("❌ Download cancelled or failed.")

    await status_msg.edit_text(f"⚙️ Trimming video from {start_time} to {end_time}...")

    ext = download_path.split('.')[-1]
    out_path = await cult_small_video(download_path, download_dir, start_time, end_time, ext)

    if not out_path:
        await delete_all(root=download_dir)
        return await status_msg.edit_text("❌ Failed to trim video.")

    await status_msg.edit_text("📤 Uploading trimmed video...")

    upload_prog = Progress(message.from_user.id, app, status_msg)

    try:
        await app.send_document(
            chat_id=message.chat.id,
            document=out_path,
            caption="Here is your trimmed video! 🎥",
            progress=upload_prog.progress_for_pyrogram,
            progress_args=("Uploading...", time.time())
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to upload trimmed video: {e}")
    finally:
        await delete_all(root=download_dir)
