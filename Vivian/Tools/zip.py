import asyncio
import os
import time
import zipfile

from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

from bot import delete_all
from config import Config
from main import LOGGER, formatDB, gDict, queueDB
from Vivian.Tools.display_progress import Progress


async def zip_and_upload(c: Client, cb: CallbackQuery, new_file_name: str):
    cb.message.reply_to_message
    vid_list = list()
    await cb.message.edit("⭕ Processing...")

    user_id = cb.from_user.id
    user_queue = queueDB.get(user_id)

    if not user_queue:
        await cb.answer("Queue Empty", show_alert=True)
        await cb.message.delete(True)
        return

    list_message_ids = []
    list_message_ids.extend(user_queue.get("videos", []))
    list_message_ids.extend(user_queue.get("audios", []))
    list_message_ids.extend(user_queue.get("subtitles", []))

    list_message_ids = [mid for mid in list_message_ids if mid is not None]

    if not list_message_ids:
        await cb.answer("Queue Empty", show_alert=True)
        await cb.message.delete(True)
        return

    download_dir = f"downloads/{str(user_id)}/"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    msgs: list[Message] = await c.get_messages(
        chat_id=user_id, message_ids=list_message_ids
    )
    msgs.sort(key=lambda x: list_message_ids.index(x.id))

    all_files = len(msgs)
    n = 1

    for i in msgs:
        media = i.video or i.document or i.audio
        if not media:
            continue

        await cb.message.edit(f"📥 Starting Download of ... `{media.file_name}`")
        LOGGER.info(f"📥 Starting Download of ... {media.file_name}")

        file_dl_path = None
        try:
            c_time = time.time()
            prog = Progress(user_id, c, cb.message)
            file_dl_path = await c.download_media(
                message=media,
                file_name=f"{download_dir}{str(i.id)}/{media.file_name}",
                progress=prog.progress_for_pyrogram,
                progress_args=(f"🚀 Downloading: `{media.file_name}`", c_time, f"\n**Downloading: {n}/{all_files}**"),
            )
            n += 1
            if gDict[cb.message.chat.id] and cb.message.id in gDict[cb.message.chat.id]:
                return
            await cb.message.edit(f"Downloaded Sucessfully ... `{media.file_name}`")
            LOGGER.info(f"Downloaded Sucessfully ... {media.file_name}")
            await asyncio.sleep(2)
        except Exception as downloadErr:
            LOGGER.warning(f"Failed to download Error: {downloadErr}")
            await cb.message.edit("❗File Skipped!")
            await asyncio.sleep(2)
            continue

        if file_dl_path:
            vid_list.append(file_dl_path)

    if not vid_list:
        await cb.message.edit("❌ Failed to download any files!")
        await delete_all(root=download_dir)
        queueDB.update(
            {user_id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({user_id: None})
        return

    await cb.message.edit("🤐 Zipping files...")

    if not new_file_name.endswith('.zip'):
        new_file_name += '.zip'

    zip_path = os.path.join(download_dir, new_file_name.rsplit(
        '/', 1)[-1] if '/' in new_file_name else new_file_name)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in vid_list:
                zipf.write(file, os.path.basename(file))
        await cb.message.edit("✅ Sucessfully Zipped Files!")
    except Exception as e:
        LOGGER.error(f"Zipping failed: {e}")
        await cb.message.edit("❌ Zipping failed!")
        await delete_all(root=download_dir)
        queueDB.update(
            {user_id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({user_id: None})
        return

    await asyncio.sleep(2)
    file_size = os.path.getsize(zip_path)

    merged_video_path = zip_path

    if file_size > 2044723200 and Config.IS_PREMIUM is False:
        await cb.message.edit(
            f"File is Larger than 2GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to add premium account to get 4GB TG uploads"
        )
        await delete_all(root=download_dir)
        queueDB.update(
            {user_id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({user_id: None})
        return

    if Config.IS_PREMIUM and file_size > 4241280205:
        await cb.message.edit(
            f"File is Larger than 4GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to die with premium account"
        )
        await delete_all(root=download_dir)
        queueDB.update(
            {user_id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({user_id: None})
        return

    try:
        c_time = time.time()
        prog = Progress(user_id, c, cb.message)
        await cb.message.edit("📤 Starting Upload...")
        await c.send_document(
            chat_id=user_id,
            document=merged_video_path,
            progress=prog.progress_for_pyrogram,
            progress_args=(f"🚀 Uploading: `{os.path.basename(merged_video_path)}`", c_time, "\n**Uploading**"),
        )
        await cb.message.delete(True)
    except Exception as e:
        LOGGER.error(f"Upload failed: {e}")
        await cb.message.edit("❌ Upload failed!")

    await delete_all(root=download_dir)
    queueDB.update({user_id: {"videos": [], "subtitles": [], "audios": []}})
    formatDB.update({user_id: None})
    return
