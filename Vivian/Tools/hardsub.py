import asyncio
import os
import time

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image
from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

from bot import delete_all
from config import Config
from main import (LOGGER, SUBTITLE_EXTENSIONS, UPLOAD_AS_DOC, VIDEO_EXTENSIONS,
                  formatDB, gDict, queueDB)
from Vivian.Function.ffmpeg import HardSubVideo, take_screen_shot
from Vivian.Function.utils import UserSettings
from Vivian.Tools.display_progress import Progress
from Vivian.Tools.uploader import uploadVideo


async def hardsub_and_upload(c: Client, cb: CallbackQuery, new_file_name: str):
    cb.message.reply_to_message
    vid_list = list()
    await cb.message.edit('⭕ Processing Hardsub...')
    user_id = cb.from_user.id
    user_queue = queueDB.get(user_id)
    if not user_queue:
        await cb.answer('Queue Empty', show_alert=True)
        await cb.message.delete(True)
        return
    video_mess = user_queue.get('videos')[0]
    list_message_ids = []
    list_message_ids.append(video_mess)
    subtitles = user_queue.get('subtitles')
    if subtitles and subtitles[0] is not None:
        list_message_ids.append(subtitles[0])
    if not list_message_ids or len(list_message_ids) < 2:
        await cb.answer('Queue needs a video and a subtitle', show_alert=True)
        await cb.message.delete(True)
        return
    download_dir = f'downloads/{str(user_id)}/'
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    msgs: list[Message] = await c.get_messages(chat_id=user_id, message_ids=list_message_ids)
    msgs.sort(key=lambda x: list_message_ids.index(x.id))
    all_files = len(msgs)
    n = 1
    for i in msgs:
        media = i.video or i.document
        if not media:
            continue
        await cb.message.edit(f'📥 Starting Download of ... `{media.file_name}`'
                              )
        LOGGER.info(f'📥 Starting Download of ... {media.file_name}')
        currentFileNameExt = media.file_name.rsplit(sep='.')[-1].lower()
        if currentFileNameExt in VIDEO_EXTENSIONS:
            tmpFileName = 'vid.mkv'
        elif currentFileNameExt in SUBTITLE_EXTENSIONS:
            tmpFileName = 'sub.' + currentFileNameExt
        else:
            tmpFileName = media.file_name
        file_dl_path = None
        try:
            c_time = time.time()
            prog = Progress(user_id, c, cb.message)
            file_dl_path = await c.download_media(message=media, file_name=f'{download_dir}{str(i.id)}/{tmpFileName}', progress=prog.
                                                  progress_for_pyrogram, progress_args=(
                f'🚀 Downloading: `{media.file_name}`', c_time,
                f"""
**Downloading: {n}/{all_files}**"""))
            n += 1
            if gDict[cb.message.chat.id] and cb.message.id in gDict[cb.
                                                                    message.chat.id]:
                return
            await cb.message.edit(
                f'Downloaded Sucessfully ... `{media.file_name}`')
            LOGGER.info(f'Downloaded Sucessfully ... {media.file_name}')
            await asyncio.sleep(2)
        except Exception as downloadErr:
            LOGGER.warning(f'Failed to download Error: {downloadErr}')
            await cb.message.edit('❗File Skipped!')
            await asyncio.sleep(2)
            continue
        if file_dl_path:
            vid_list.append(file_dl_path)
    if len(vid_list) < 2:
        await cb.message.edit('❌ Failed to download required files!')
        await delete_all(root=download_dir)
        queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}}
                       )
        formatDB.update({user_id: None})
        return
    await cb.message.edit(
        '⚙️ Burning subtitles (Hardsub)... This will take a while.')
    hardsubbed_video = os.path.join(download_dir, 'hardsubbed.mp4')
    video_path = vid_list[0] if 'vid.mkv' in vid_list[0] else vid_list[1]
    sub_path = vid_list[1] if 'sub.' in vid_list[1] else vid_list[0]
    success = await HardSubVideo(video_path, sub_path, hardsubbed_video)
    if not success:
        await cb.message.edit('❌ Hardsub failed!')
        await delete_all(root=download_dir)
        queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}}
                       )
        formatDB.update({user_id: None})
        return
    await cb.message.edit('✅ Sucessfully Hardsubbed Video!')
    await asyncio.sleep(2)
    file_size = os.path.getsize(hardsubbed_video)
    os.rename(hardsubbed_video, new_file_name)
    await cb.message.edit(
        f"🔄 Renaming Video to\n **{new_file_name.rsplit('/', 1)[-1]}**")
    await asyncio.sleep(2)
    merged_video_path = new_file_name
    if file_size > 2044723200 and Config.IS_PREMIUM is False:
        await cb.message.edit(
            f"""File is Larger than 2GB Can't Upload,

 Tell {Config.OWNER_USERNAME} to add premium account to get 4GB TG uploads"""
        )
        await delete_all(root=download_dir)
        queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}}
                       )
        formatDB.update({user_id: None})
        return
    if Config.IS_PREMIUM and file_size > 4241280205:
        await cb.message.edit(
            f"""File is Larger than 4GB Can't Upload,

 Tell {Config.OWNER_USERNAME} to die with premium account"""
        )
        await delete_all(root=download_dir)
        queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}}
                       )
        formatDB.update({user_id: None})
        return
    await cb.message.edit('🎥 Extracting Video Data ...')
    duration = 1
    try:
        metadata = extractMetadata(createParser(merged_video_path))
        if metadata.has('duration'):
            duration = metadata.get('duration').seconds
    except Exception:
        await delete_all(root=download_dir)
        queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}}
                       )
        formatDB.update({user_id: None})
        await cb.message.edit('⭕ Merged Video is corrupted')
        return
    try:
        user = UserSettings(user_id, cb.from_user.first_name)
        thumb_id = user.thumbnail
        if thumb_id is None:
            raise Exception
        video_thumbnail = f'{download_dir}_thumb.jpg'
        await c.download_media(message=str(thumb_id), file_name=video_thumbnail
                               )
    except Exception:
        LOGGER.info('Generating thumb')
        video_thumbnail = await take_screen_shot(merged_video_path,
                                                 download_dir, duration / 2)
    width = 1280
    height = 720
    try:
        thumb = extractMetadata(createParser(video_thumbnail))
        height = thumb.get('height')
        width = thumb.get('width')
        img = Image.open(video_thumbnail)
        if width > height:
            img.resize((320, height))
        elif height > width:
            img.resize((width, 320))
        img.save(video_thumbnail)
        Image.open(video_thumbnail).convert('RGB').save(video_thumbnail, 'JPEG'
                                                        )
    except BaseException:
        await delete_all(root=download_dir)
        queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}}
                       )
        formatDB.update({user_id: None})
        await cb.message.edit(
            """⭕ Merged Video is corrupted

<i>Try setting custom thumbnail</i>"""
        )
        return
    await uploadVideo(c=c, cb=cb, merged_video_path=merged_video_path,
                      width=width, height=height, duration=duration, video_thumbnail=video_thumbnail, file_size=os.path.getsize(merged_video_path),
                      upload_mode=UPLOAD_AS_DOC.get(f'{user_id}', False))
    await cb.message.delete(True)
    await delete_all(root=download_dir)
    queueDB.update({user_id: {'videos': [], 'subtitles': [], 'audios': []}})
    formatDB.update({user_id: None})
    return
