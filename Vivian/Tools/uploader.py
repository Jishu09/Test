import time

import aiohttp
from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

from bot import LOGCHANNEL, userBot
from config import Config
from main import LOGGER, UPLOAD_DESTINATION
from Vivian.Tools.display_progress import Progress


async def upload_to_gofile(file_path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.gofile.io/servers') as resp:
                data = await resp.json()
                if data.get('status') != 'ok':
                    return None
                server = data['data']['servers'][0]['name']

            with open(file_path, 'rb') as f:
                form_data = aiohttp.FormData()
                form_data.add_field('file', f)
                if Config.GOFILE_TOKEN:
                    form_data.add_field('token', Config.GOFILE_TOKEN)

                url = f'https://{server}.gofile.io/contents/uploadfile'
                async with session.post(url, data=form_data) as resp:
                    result = await resp.json()
                    if result.get('status') == 'ok':
                        return result['data']['downloadPage']
                    else:
                        LOGGER.error(f"Gofile upload failed: {result}")
                        return None
    except Exception as e:
        LOGGER.error(f"Gofile upload error: {e}")
        return None


async def uploadVideo(
    c: Client,
    cb: CallbackQuery,
    merged_video_path,
    width,
    height,
    duration,
    video_thumbnail,
    file_size,
    upload_mode: bool,
):
    dest = UPLOAD_DESTINATION.get(f"{cb.from_user.id}", "telegram")

    if dest == "gofile":
        await cb.message.edit(f"Uploading to GoFile: `{merged_video_path.rsplit('/', 1)[-1]}`")
        link = await upload_to_gofile(merged_video_path)
        if link:
            await cb.message.reply_text(f"File uploaded to GoFile:\n\n{link}", quote=True)
            await cb.message.delete()
        else:
            await cb.message.edit("Failed to upload to GoFile.")
        return

    if Config.IS_PREMIUM:
        sent_ = None
        prog = Progress(cb.from_user.id, c, cb.message)
        async with userBot:
            if upload_mode is False:
                c_time = time.time()
                sent_: Message = await userBot.send_video(
                    chat_id=int(LOGCHANNEL),
                    video=merged_video_path,
                    height=height,
                    width=width,
                    duration=duration,
                    thumb=video_thumbnail,
                    caption=f"`{merged_video_path.rsplit('/', 1)[-1]}`\n\nMerged for: {cb.from_user.mention}",
                    progress=prog.progress_for_pyrogram,
                    progress_args=(
                        f"Uploading: `{merged_video_path.rsplit('/', 1)[-1]}`",
                        c_time,
                    ),
                )
            else:
                c_time = time.time()
                sent_: Message = await userBot.send_document(
                    chat_id=int(LOGCHANNEL),
                    document=merged_video_path,
                    thumb=video_thumbnail,
                    caption=f"`{merged_video_path.rsplit('/', 1)[-1]}`\n\nMerged for: <a href='tg://user?id={cb.from_user.id}'>{cb.from_user.first_name}</a>",
                    progress=prog.progress_for_pyrogram,
                    progress_args=(
                        f"Uploading: `{merged_video_path.rsplit('/', 1)[-1]}`",
                        c_time,
                    ),
                )
            if sent_ is not None:
                await c.copy_message(
                    chat_id=cb.message.chat.id,
                    from_chat_id=sent_.chat.id,
                    message_id=sent_.id,
                    caption=f"`{merged_video_path.rsplit('/', 1)[-1]}`",
                )

    else:
        try:
            sent_ = None
            prog = Progress(cb.from_user.id, c, cb.message)
            if upload_mode is False:
                c_time = time.time()
                sent_: Message = await c.send_video(
                    chat_id=cb.message.chat.id,
                    video=merged_video_path,
                    height=height,
                    width=width,
                    duration=duration,
                    thumb=video_thumbnail,
                    caption=f"`{merged_video_path.rsplit('/', 1)[-1]}`",
                    progress=prog.progress_for_pyrogram,
                    progress_args=(
                        f"Uploading: `{merged_video_path.rsplit('/', 1)[-1]}`",
                        c_time,
                    ),
                )
            else:
                c_time = time.time()
                sent_: Message = await c.send_document(
                    chat_id=cb.message.chat.id,
                    document=merged_video_path,
                    thumb=video_thumbnail,
                    caption=f"`{merged_video_path.rsplit('/', 1)[-1]}`",
                    progress=prog.progress_for_pyrogram,
                    progress_args=(
                        f"Uploading: `{merged_video_path.rsplit('/', 1)[-1]}`",
                        c_time,
                    ),
                )
        except Exception as err:
            LOGGER.info(err)
            await cb.message.edit("Failed to upload")
        if sent_ is not None:
            if Config.LOGCHANNEL is not None:
                media = sent_.video or sent_.document
                await sent_.copy(
                    chat_id=int(LOGCHANNEL),
                    caption=f"`{media.file_name}`\n\nMerged for: <a href='tg://user?id={cb.from_user.id}'>{cb.from_user.first_name}</a>",
                )


async def uploadFiles(
    c: Client,
    cb: CallbackQuery,
    up_path,
    n,
    all
):
    dest = UPLOAD_DESTINATION.get(f"{cb.from_user.id}", "telegram")
    if dest == "gofile":
        await cb.message.edit(f"Uploading to GoFile: `{up_path.rsplit('/', 1)[-1]}`\n**Uploading: {n}/{all}**")
        link = await upload_to_gofile(up_path)
        if link:
            await cb.message.reply_text(f"File uploaded to GoFile:\n\n{link}", quote=True)
            await cb.message.delete()
        else:
            await cb.message.edit("Failed to upload to GoFile.")
        return

    try:
        sent_ = None
        prog = Progress(cb.from_user.id, c, cb.message)
        c_time = time.time()
        sent_: Message = await c.send_document(
            chat_id=cb.message.chat.id,
            document=up_path,
            caption=f"`{up_path.rsplit('/', 1)[-1]}`",
            progress=prog.progress_for_pyrogram,
            progress_args=(
                f"Uploading: `{up_path.rsplit('/', 1)[-1]}`",
                c_time,
                f"\n**Uploading: {n}/{all}**"
            ),
        )
        if sent_ is not None:
            if Config.LOGCHANNEL is not None:
                media = sent_.video or sent_.document
                await sent_.copy(
                    chat_id=int(LOGCHANNEL),
                    caption=f"`{media.file_name}`\n\nExtracted by: <a href='tg://user?id={cb.from_user.id}'>{cb.from_user.first_name}</a>",
                )
    except BaseException:
        1
    1
