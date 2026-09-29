import asyncio
import os
import shutil
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from main import UPLOAD_AS_DOC
from Vivian.Tools.display_progress import Progress
from Vivian.Tools.video_tools import simple_handler


def is_auth(message: Message) -> bool:
    return message.chat.id == int(Config.OWNER)


async def run_cmd(cmd):
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.
                                                subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout, stderr


async def process_media(app, message, processing_func,
                        status_text='⚙️ Processing...'):
    if not is_auth(message):
        return await message.reply_text('🚫 Admin Only')
    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document or message.reply_to_message.audio):
        return await message.reply_text('Please reply to a media message.')
    media = (message.reply_to_message.video or message.reply_to_message.
             document or message.reply_to_message.audio)
    status_msg = await message.reply_text('📥 Downloading...', quote=True)
    prog = Progress(message.from_user.id, app, status_msg)
    download_dir = f'downloads/{message.from_user.id}_tmp_{time.time()}/'
    os.makedirs(download_dir, exist_ok=True)
    file_name = getattr(media, 'file_name', None) or 'media'
    try:
        download_path = await app.download_media(message=message.
                                                 reply_to_message, file_name=f'{download_dir}{file_name}',
                                                 progress=prog.progress_for_pyrogram, progress_args=(
                                                     'Downloading...', time.time()))
    except Exception as e:
        shutil.rmtree(download_dir, ignore_errors=True)
        return await status_msg.edit_text(f'❌ Download failed: {e}')
    if not download_path:
        shutil.rmtree(download_dir, ignore_errors=True)
        return await status_msg.edit_text('❌ Download cancelled.')
    await status_msg.edit_text(status_text)
    try:
        out_paths = await processing_func(download_path, download_dir)
        if not out_paths:
            raise Exception('Output file not found after processing.')
        if not isinstance(out_paths, list):
            out_paths = [out_paths]
        await status_msg.edit_text('📤 Uploading...')
        for p in out_paths:
            if not os.path.exists(p):
                continue
            upload_prog = Progress(message.from_user.id, app, status_msg)
            ext = p.lower().rsplit('.', 1)[-1] if '.' in p else ''
            if ext in ('jpg', 'jpeg', 'png'):
                await app.send_photo(chat_id=message.chat.id, photo=p,
                                     reply_to_message_id=message.reply_to_message.id,
                                     progress=upload_prog.progress_for_pyrogram,
                                     progress_args=('Uploading...', time.time()))
            elif ext in ('mp4', 'mkv', 'webm', 'avi'
                         ) and not UPLOAD_AS_DOC.get(f'{message.from_user.id}', False):
                await app.send_video(chat_id=message.chat.id, video=p,
                                     reply_to_message_id=message.reply_to_message.id,
                                     progress=upload_prog.progress_for_pyrogram,
                                     progress_args=('Uploading...', time.time()))
            elif ext in ('mp3', 'm4a', 'flac', 'wav', 'aac'
                         ) and not UPLOAD_AS_DOC.get(f'{message.from_user.id}', False):
                await app.send_audio(chat_id=message.chat.id, audio=p,
                                     reply_to_message_id=message.reply_to_message.id,
                                     progress=upload_prog.progress_for_pyrogram,
                                     progress_args=('Uploading...', time.time()))
            else:
                await app.send_document(chat_id=message.chat.id, document=p,
                                        reply_to_message_id=message.reply_to_message.id,
                                        progress=upload_prog.progress_for_pyrogram,
                                        progress_args=('Uploading...', time.time()))
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f'❌ Error: {e}')
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


@Client.on_message(filters.incoming & filters.command(['extractthumb']))
async def extractthumb_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text('🚫 Admin Only')
    if not message.reply_to_message:
        return await message.reply_text('Reply to a media.')
    media = message.reply_to_message.video or message.reply_to_message.document
    if not media:
        return await message.reply_text('No media found.')
    if hasattr(media, 'thumbs') and media.thumbs:
        thumb_id = media.thumbs[0].file_id
        await app.send_photo(message.chat.id, thumb_id, reply_to_message_id=message.reply_to_message.id)
    else:

        async def process(in_path, d_dir):
            out = os.path.join(d_dir, 'thumb.jpg')
            cmd = ['ffmpeg', '-i', in_path, '-ss', '00:00:01', '-vframes',
                   '1', out, '-y']
            ret, stdout, stderr = await run_cmd(cmd)
            if ret != 0:
                raise Exception(
                    f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
            return out
        await process_media(app, message, process, '⚙️ Extracting Thumbnail...'
                            )


@Client.on_message(filters.incoming & filters.command(['caption']))
async def caption_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text('🚫 Admin Only')
    if not message.reply_to_message:
        return await message.reply_text('Reply to a media.')
    new_caption = message.text.split(' ', 1)[1] if len(message.text.split(' ')
                                                       ) > 1 else ''
    try:
        await message.reply_to_message.copy(message.chat.id, caption=new_caption)
    except Exception as e:
        await message.reply_text(f'Error: {e}')


@Client.on_message(filters.incoming & filters.command(['mapstream']))
async def mapstream_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text(
            'Usage: /mapstream <map_args> (e.g. 0:v 0:a:1)')
    map_args = args[1].split(' ')

    async def process(in_path, d_dir):
        out = os.path.join(d_dir, 'mapped_' + os.path.basename(in_path))
        cmd = ['ffmpeg', '-i', in_path]
        for m in map_args:
            cmd.extend(['-map', m])
        cmd.extend(['-c', 'copy', out, '-y'])
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, '⚙️ Mapping streams...')


@Client.on_message(filters.incoming & filters.command(['removestream']))
async def removestream_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text(
            'Usage: /removestream <stream_index> (e.g. 1)')
    idx = args[1]

    async def process(in_path, d_dir):
        out = os.path.join(d_dir, 'removed_' + os.path.basename(in_path))
        cmd = ['ffmpeg', '-i', in_path, '-map', '0', '-map', f'-0:{idx}',
               '-c', 'copy', out, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, '⚙️ Removing stream...')


@Client.on_message(filters.incoming & filters.command(['removeaudio']))
async def removeaudio_handler(app: Client, message: Message):

    async def process(in_path, d_dir):
        out = os.path.join(d_dir, 'noaudio_' + os.path.basename(in_path))
        cmd = ['ffmpeg', '-i', in_path, '-c', 'copy', '-an', out, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, '⚙️ Removing audio...')


@Client.on_message(filters.incoming & filters.command(['convertaudio']))
async def convertaudio_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text(
            'Usage: /convertaudio <format> (e.g. mp3)')
    fmt = os.path.basename(args[1])

    async def process(in_path, d_dir):
        name = os.path.splitext(os.path.basename(in_path))[0]
        out = os.path.join(d_dir, f'{name}.{fmt}')
        cmd = ['ffmpeg', '-i', in_path, out, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, '⚙️ Converting audio...')


@Client.on_message(filters.incoming & filters.command(['split']))
async def split_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text('Usage: /split <time> (e.g. 00:05:00)')
    split_time = args[1]

    async def process(in_path, d_dir):
        name = os.path.splitext(os.path.basename(in_path))[0]
        ext = os.path.splitext(in_path)[1]
        out_pattern = os.path.join(d_dir, f'{name}_%03d{ext}')
        cmd = ['ffmpeg', '-i', in_path, '-c', 'copy', '-map', '0',
               '-segment_time', split_time, '-f', 'segment',
               '-reset_timestamps', '1', out_pattern, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return sorted([os.path.join(d_dir, f) for f in os.listdir(d_dir) if
                       f != os.path.basename(in_path)])
    await process_media(app, message, process, '⚙️ Splitting video...')


@Client.on_message(filters.incoming & filters.command(['manualshot']))
async def manualshot_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text(
            'Usage: /manualshot <time> (e.g. 00:01:23)')
    shot_time = args[1]

    async def process(in_path, d_dir):
        out = os.path.join(d_dir, 'shot.jpg')
        cmd = ['ffmpeg', '-i', in_path, '-ss', shot_time, '-vframes', '1',
               out, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, '⚙️ Taking screenshot...')


@Client.on_message(filters.incoming & filters.command(['sample']))
async def sample_handler(app: Client, message: Message):
    await simple_handler(app, message)


@Client.on_message(filters.incoming & filters.command(['v2a']))
async def v2a_handler(app: Client, message: Message):

    async def process(in_path, d_dir):
        name = os.path.splitext(os.path.basename(in_path))[0]
        out = os.path.join(d_dir, f'{name}.mp3')
        cmd = ['ffmpeg', '-i', in_path, '-q:a', '0', '-map', 'a', out, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, '⚙️ Extracting Audio...')


@Client.on_message(filters.incoming & filters.command(['convert']))
async def convert_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text(
            'Usage: /convert <format> (e.g. mkv, mp4)')
    fmt = os.path.basename(args[1].strip())
    if fmt.startswith('.'):
        fmt = fmt[1:]

    async def process(in_path, d_dir):
        name = os.path.splitext(os.path.basename(in_path))[0]
        out = os.path.join(d_dir, f'{name}.{fmt}')
        cmd = ['ffmpeg', '-i', in_path, '-c', 'copy', out, '-y']
        ret, stdout, stderr = await run_cmd(cmd)
        if ret != 0:
            raise Exception(
                f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
        return out
    await process_media(app, message, process, f'⚙️ Converting to {fmt}...')


@Client.on_message(filters.incoming & filters.command(['rename']))
async def rename_handler(app: Client, message: Message):
    args = message.text.split(' ', 1)
    if len(args) < 2:
        return await message.reply_text('Usage: /rename <new_name.ext>')
    new_name = os.path.basename(args[1])

    async def process(in_path, d_dir):
        out = os.path.join(d_dir, new_name)
        os.rename(in_path, out)
        return out
    await process_media(app, message, process, '⚙️ Renaming...')


@Client.on_message(filters.incoming & filters.command(['mediainfo']))
async def mediainfo_handler(app: Client, message: Message):
    if not is_auth(message):
        return await message.reply_text('🚫 Admin Only')
    if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document or message.reply_to_message.audio):
        return await message.reply_text('Please reply to a media message.')
    media = (message.reply_to_message.video or message.reply_to_message.
             document or message.reply_to_message.audio)
    status_msg = await message.reply_text('📥 Downloading to extract info...',
                                          quote=True)
    prog = Progress(message.from_user.id, app, status_msg)
    download_dir = f'downloads/{message.from_user.id}_tmp_{time.time()}/'
    os.makedirs(download_dir, exist_ok=True)
    file_name = getattr(media, 'file_name', None) or 'media'
    try:
        download_path = await app.download_media(message=message.
                                                 reply_to_message, file_name=f'{download_dir}{file_name}',
                                                 progress=prog.progress_for_pyrogram, progress_args=(
                                                     'Downloading...', time.time()))
    except Exception as e:
        shutil.rmtree(download_dir, ignore_errors=True)
        return await status_msg.edit_text(f'❌ Download failed: {e}')
    if not download_path:
        shutil.rmtree(download_dir, ignore_errors=True)
        return await status_msg.edit_text('❌ Download cancelled.')
    await status_msg.edit_text('⚙️ Extracting Media Info...')
    try:
        proc = await asyncio.create_subprocess_exec('ffprobe',
                                                    '-hide_banner', '-i', download_path, stdout=asyncio.subprocess.
                                                    PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        info_text = stderr.decode('utf-8', errors='ignore')
        lines = info_text.split('\n')
        useful_lines = []
        capture = False
        for line in lines:
            if 'Input #0' in line:
                capture = True
            if capture:
                useful_lines.append(line)
        final_text = '\n'.join(useful_lines)
        if len(final_text) > 4000:
            final_text = final_text[:4000] + '...'
        await status_msg.edit_text(f'**Media Info:**\n```\n{final_text}\n```')
    except Exception as e:
        await status_msg.edit_text(f'❌ Error: {e}')
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)
