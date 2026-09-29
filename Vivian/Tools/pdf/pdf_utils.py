import asyncio
import os
import shutil

import img2pdf
from pyrogram.types import CallbackQuery

from main import LOGGER, queueDB


async def create_pdf_from_images(c, cb: CallbackQuery, pdf_name="merged.pdf"):
    user_id = cb.from_user.id

    if not queueDB.get(user_id) or not queueDB.get(user_id)["videos"]:
        await cb.message.edit_text("Queue is empty. No photos to create PDF.")
        return

    msg = await cb.message.edit_text("Downloading photos...")

    dir_path = f"downloads/{user_id}/pdf"
    os.makedirs(dir_path, exist_ok=True)

    img_paths = []

    try:
        msg_ids = queueDB[user_id]["videos"]
        messages = await c.get_messages(chat_id=cb.message.chat.id, message_ids=msg_ids)
        messages.sort(key=lambda x: msg_ids.index(x.id))
        for i, m in enumerate(messages):
            if m.empty:
                continue
            if m.photo or (
                    m.document and m.document.mime_type.startswith("image/")):
                file_path = await c.download_media(message=m, file_name=f"{dir_path}/image_{i}.jpg")
                img_paths.append(file_path)

        if not img_paths:
            await msg.edit_text("No valid images found to create PDF.")
            return

        await msg.edit_text("Creating PDF...")

        pdf_path = f"{dir_path}/{pdf_name}"

        def write_pdf():
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(img_paths))
        await asyncio.to_thread(write_pdf)

        await msg.edit_text("Uploading PDF...")
        await c.send_document(chat_id=cb.message.chat.id, document=pdf_path)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"Error creating PDF: {e}")
        LOGGER.error(e)
    finally:
        queueDB.update(
            {user_id: {"videos": [], "subtitles": [], "audios": []}})
        shutil.rmtree(dir_path, ignore_errors=True)
