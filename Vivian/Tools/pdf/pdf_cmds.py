import asyncio
import os
import shutil

import pymupdf
from pyrogram import Client, StopPropagation, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from main import LOGGER, formatDB, queueDB


def is_auth(message: Message) -> bool:
    return message.from_user.id == int(Config.OWNER)


@Client.on_message(filters.incoming & filters.command(['pdf']))
async def pdf_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text('🚫 Admin Only')
    user_id = message.from_user.id
    queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}})
    formatDB.update({user_id: None})
    await message.reply_text(
        'Send photos or images to create a PDF. Send /done when you are finished.'
    )
    q = asyncio.Queue()

    async def _queue_handler(client, msg):
        if msg.chat.id == message.chat.id:
            await q.put(msg)
            raise StopPropagation
    handler = MessageHandler(_queue_handler, filters=filters.incoming & (
        filters.photo | filters.document | filters.text))
    app.add_handler(handler, group=-1)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=300)
            except asyncio.TimeoutError:
                await message.reply_text(
                    'Timeout waiting for files. Queue cleared.')
                queueDB.update({user_id: {'videos': [], 'subtitles': [],
                                          'audios': []}})
                formatDB.update({user_id: None})
                break
            if msg.text and msg.text.startswith('/done'):
                break
            if msg.photo or msg.document:
                queueDB[user_id]['videos'].append(msg.id)
                await message.reply_text(
                    f"Added to PDF queue. Total images: {len(queueDB[user_id]['videos'])}"
                )
    finally:
        app.remove_handler(handler, group=-1)
    if not queueDB.get(user_id)['videos']:
        await message.reply_text('No images were added to the queue.')
        return
    await message.reply_text(text='Do you want to create a PDF now?',
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                                 '📤 Create PDF', callback_data='create_pdf')], [InlineKeyboardButton
                                                                                ('⛔ Cancel ⛔', callback_data='cancel')]]), quote=True)


@Client.on_message(filters.incoming & filters.command(['cpdf']))
async def cpdf_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text('🚫 Admin Only')
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text(
            'Please reply to a PDF file with /cpdf to convert it to images.')
    if not message.reply_to_message.document.file_name.lower().endswith('.pdf'
                                                                        ):
        return await message.reply_text('The replied file is not a PDF.')
    msg = await message.reply_text('Downloading PDF...')
    user_id = message.from_user.id
    dir_path = f'downloads/{user_id}/cpdf'
    os.makedirs(dir_path, exist_ok=True)
    pdf_path = f'{dir_path}/file.pdf'
    await app.download_media(message.reply_to_message, file_name=pdf_path)
    await msg.edit_text('Converting PDF to images...')
    try:
        doc = await asyncio.to_thread(pymupdf.open, pdf_path)
        for page_num in range(len(doc)):
            page = await asyncio.to_thread(doc.load_page, page_num)
            pix = await asyncio.to_thread(page.get_pixmap)
            img_path = f'{dir_path}/page_{page_num + 1}.png'
            await asyncio.to_thread(pix.save, img_path)
            await app.send_document(chat_id=message.chat.id, document=img_path)
        await msg.edit_text('Conversion complete!')
    except Exception as e:
        await msg.edit_text(f'Error during conversion: {e}')
        LOGGER.error(e)
    finally:
        shutil.rmtree(dir_path, ignore_errors=True)
