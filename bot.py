import asyncio
import os
import shutil
import time
from collections import OrderedDict

import psutil
import pyrogram.dispatcher
from aiohttp import web
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image
from pyrogram import Client, enums, filters
from pyrogram.errors import (FloodWait, InputUserDeactivated, PeerIdInvalid,
                             UserIsBlocked)
from pyrogram.handlers import MessageHandler
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message, User)

from config import Config
from main import (AUDIO_EXTENSIONS, BROADCAST_MSG, LOGGER, SUBTITLE_EXTENSIONS,
                  UPLOAD_AS_DOC, VIDEO_EXTENSIONS, bMaker, formatDB, queueDB,
                  replyDB)
from Vivian.Database import database
from Vivian.Database.database import getEncodeSettings
from Vivian.Function.ffmpeg import encode_video, take_screen_shot
from Vivian.Function.listener import listen
from Vivian.Function.utils import (UserSettings, get_readable_file_size,
                                   get_readable_time)
from Vivian.Tools.display_progress import Progress
from Vivian.Tools.encode import process_encode
from Vivian.Tools.uploader import uploadVideo


def new_add_handler(self, handler, group=0):
    if group not in self.groups:
        self.groups[group] = []
        self.groups = OrderedDict(sorted(self.groups.items()))
    self.groups[group].append(handler)


def new_remove_handler(self, handler, group=0):
    if group in self.groups:
        self.groups[group].remove(handler)
        if not self.groups[group]:
            del self.groups[group]


pyrogram.dispatcher.Dispatcher.add_handler = new_add_handler
pyrogram.dispatcher.Dispatcher.remove_handler = new_remove_handler
botStartTime = time.time()


class MergeBot(Client):

    async def start(self):
        await super().start()
        try:
            await self.send_message(chat_id=int(Config.OWNER), text='<b>Bot Started!</b>')
        except Exception:
            LOGGER.error('Boot alert failed! Please start bot in PM')
        return LOGGER.info('Bot Started!')

    async def stop(self):
        await super().stop()
        return LOGGER.info('Bot Stopped')


if os.path.exists('downloads') is False:
    os.makedirs('downloads')


async def sendLogFile(c: Client, m: Message):
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    await m.reply_document(document='./mergebotlog.txt')
    return


async def stats_handler(c: Client, m: Message):
    currentTime = get_readable_time(time.time() - botStartTime)
    total, used, free = shutil.disk_usage('.')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    cpuUsage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    stats = f"""<b>╭「 💠 BOT STATISTICS 」</b>
<b>│</b>
<b>├⏳ Bot Uptime : {currentTime}</b>
<b>├💾 Total Disk Space : {total}</b>
<b>├📀 Total Used Space : {used}</b>
<b>├💿 Total Free Space : {free}</b>
<b>├🔺 Total Upload : {sent}</b>
<b>├🔻 Total Download : {recv}</b>
<b>├🖥 CPU : {cpuUsage}%</b>
<b>├⚙️ RAM : {memory}%</b>
<b>╰💿 DISK : {disk}%</b>"""
    await m.reply_text(text=stats, quote=True)


async def broadcast_handler(c: Client, m: Message):
    msg = m.reply_to_message
    userList = await database.broadcast()
    len = userList.collection.count_documents({})
    status = await m.reply_text(text=BROADCAST_MSG.format(str(len), '0'),
                                quote=True)
    success = 0
    for i in range(len):
        try:
            uid = userList[i]['_id']
            if uid != int(Config.OWNER):
                await msg.copy(chat_id=uid)
            success = i + 1
            await status.edit_text(text=BROADCAST_MSG.format(len, success))
            LOGGER.info(f"Message sent to {userList[i]['name']} ")
        except FloodWait as e:
            await asyncio.sleep(e.x)
            await msg.copy(chat_id=userList[i]['_id'])
            LOGGER.info(f"Message sent to {userList[i]['name']} ")
        except InputUserDeactivated:
            await database.deleteUser(userList[i]['_id'])
            LOGGER.info(
                f"{userList[i]['_id']} - {userList[i]['name']} : deactivated\n"
            )
        except UserIsBlocked:
            await database.deleteUser(userList[i]['_id'])
            LOGGER.info(
                f"{userList[i]['_id']} - {userList[i]['name']} : blocked the bot\n"
            )
        except PeerIdInvalid:
            await database.deleteUser(userList[i]['_id'])
            LOGGER.info(
                f"{userList[i]['_id']} - {userList[i]['name']} : user id invalid\n"
            )
        except Exception as err:
            LOGGER.warning(f'{err}\n')
        await asyncio.sleep(3)
    await status.edit_text(text=BROADCAST_MSG.format(len, success) +
                           f"""**Failed: {str(len - success)}**

__🤓 Broadcast completed sucessfully__"""
                           )


async def files_handler(c: Client, m: Message):
    user_id = m.from_user.id
    user = UserSettings(user_id, m.from_user.first_name)
    if user_id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    if user.merge_mode == 4:
        return
    input_ = f'downloads/{str(user_id)}/input.txt'
    if os.path.exists(input_):
        await m.reply_text(
            "Sorry Bro,\nAlready One process in Progress!\nDon't Spam.")
        return
    media = m.video or m.document or m.audio
    if media.file_name is None:
        await m.reply_text('File Not Found')
        return
    currentFileNameExt = media.file_name.rsplit(sep='.')[-1].lower(
    ) if media.file_name else None
    if user.merge_mode == 1:
        if queueDB.get(user_id, None) is None:
            formatDB.update({user_id: currentFileNameExt})
        if formatDB.get(
                user_id,
                None) is not None and currentFileNameExt != formatDB.get(user_id):
            await m.reply_text(
                f'First you sent a {formatDB.get(user_id).upper()} file so now send only that type of file.', quote=True)
            return
        if (not currentFileNameExt or currentFileNameExt not in
                VIDEO_EXTENSIONS):
            await m.reply_text(
                'This Video Format not Allowed!\nOnly send MP4 or MKV or WEBM.', quote=True)
            return
        editable = await m.reply_text('Please Wait ...', quote=True)
        MessageText = (
            'Okay,\nNow Send Me Next Video or Press **Merge Now** Button!')
        if queueDB.get(user_id, None) is None:
            queueDB.update({user_id: {'videos': [], 'subtitles': [],
                                      'audios': []}})
        if len(queueDB.get(user_id)['videos']) >= 0 and len(queueDB.get(
                user_id)['videos']) < 10:
            queueDB.get(user_id)['videos'].append(m.id)
            queueDB.get(m.from_user.id)['subtitles'].append(None)
            if len(queueDB.get(user_id)['videos']) == 1:
                reply_ = await editable.edit(
                    '**Send me some more videos to merge them into single file**', reply_markup=InlineKeyboardMarkup(bMaker.makebuttons(
                        ['Cancel'], ['cancel'])))
                replyDB.update({user_id: reply_.id})
                return
            if queueDB.get(user_id, None)['videos'] is None:
                formatDB.update({user_id: currentFileNameExt})
            if replyDB.get(user_id, None) is not None:
                await c.delete_messages(chat_id=m.chat.id, message_ids=replyDB.get(user_id))
            if len(queueDB.get(user_id)['videos']) == 10:
                MessageText = 'Okay, Now Just Press **Merge Now** Button Plox!'
            markup = await makeButtons(c, m, queueDB)
            reply_ = await editable.edit(text=MessageText, reply_markup=InlineKeyboardMarkup(markup))
            replyDB.update({user_id: reply_.id})
        elif len(queueDB.get(user_id)['videos']) > 10:
            markup = await makeButtons(c, m, queueDB)
            await editable.text('Max 10 videos allowed', reply_markup=InlineKeyboardMarkup(markup))
    elif user.merge_mode == 2:
        editable = await m.reply_text('Please Wait ...', quote=True)
        MessageText = (
            'Okay,\nNow Send Me Some More <u>Audios</u> or Press **Merge Now** Button!'
        )
        if queueDB.get(user_id, None) is None:
            queueDB.update({user_id: {'videos': [], 'subtitles': [],
                                      'audios': []}})
        if len(queueDB.get(user_id)['videos']) == 0:
            queueDB.get(user_id)['videos'].append(m.id)
            reply_ = await editable.edit(text='Now, Send all the audios you want to merge', reply_markup=InlineKeyboardMarkup(bMaker.makebuttons(['Cancel'], [
                'cancel'])))
            replyDB.update({user_id: reply_.id})
            return
        elif len(queueDB.get(user_id)['videos']
                 ) >= 1 and currentFileNameExt in AUDIO_EXTENSIONS:
            queueDB.get(user_id)['audios'].append(m.id)
            if replyDB.get(user_id, None) is not None:
                await c.delete_messages(chat_id=m.chat.id, message_ids=replyDB.get(user_id))
            markup = await makeButtons(c, m, queueDB)
            reply_ = await editable.edit(text=MessageText, reply_markup=InlineKeyboardMarkup(markup))
            replyDB.update({user_id: reply_.id})
        else:
            await m.reply('This Filetype is not valid')
            return
    elif user.merge_mode == 3:
        editable = await m.reply_text('Please Wait ...', quote=True)
        MessageText = """Okay,
Now Send Me Some More <u>Subtitles</u> or Press **Merge Now** Button!"""
        if queueDB.get(user_id, None) is None:
            queueDB.update({user_id: {'videos': [], 'subtitles': [],
                                      'audios': []}})
        if len(queueDB.get(user_id)['videos']) == 0:
            queueDB.get(user_id)['videos'].append(m.id)
            reply_ = await editable.edit(text='Now, Send all the subtitles you want to merge',
                                         reply_markup=InlineKeyboardMarkup(bMaker.makebuttons([
                                             'Cancel'], ['cancel'])))
            replyDB.update({user_id: reply_.id})
            return
        elif len(queueDB.get(user_id)['videos']
                 ) >= 1 and currentFileNameExt in SUBTITLE_EXTENSIONS:
            queueDB.get(user_id)['subtitles'].append(m.id)
            if replyDB.get(user_id, None) is not None:
                await c.delete_messages(chat_id=m.chat.id, message_ids=replyDB.get(user_id))
            markup = await makeButtons(c, m, queueDB)
            reply_ = await editable.edit(text=MessageText, reply_markup=InlineKeyboardMarkup(markup))
            replyDB.update({user_id: reply_.id})
        else:
            await m.reply('This Filetype is not valid')
            return
    elif user.merge_mode == 5:
        if (not currentFileNameExt or currentFileNameExt not in
                VIDEO_EXTENSIONS):
            await m.reply_text(
                'This Video Format not Allowed!\nOnly send MP4 or MKV or WEBM.', quote=True)
            return
        if not os.path.exists(f'downloads/{str(user_id)}/'):
            os.makedirs(f'downloads/{str(user_id)}/')
        with open(input_, 'w') as f:
            f.write('lock')
        try:
            await process_encode(c, m, m)
        finally:
            if os.path.exists(input_):
                os.remove(input_)


async def photo_handler(c: Client, m: Message):
    user = UserSettings(m.chat.id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        del user
        return
    thumbnail = m.photo.file_id
    msg = await m.reply_text('Saving Thumbnail. . . .', quote=True)
    user.thumbnail = thumbnail
    user.set()
    LOCATION = f'downloads/{m.from_user.id}_thumb.jpg'
    await c.download_media(message=m, file_name=LOCATION)
    await msg.edit_text(text='✅ Custom Thumbnail Saved!')
    del user


async def zip_handler(c: Client, m: Message):
    user_id = m.from_user.id
    UserSettings(user_id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    if queueDB.get(user_id, None) is None or not queueDB.get(user_id).get(
            'videos', []) and not queueDB.get(user_id).get('audios', []):
        await m.reply_text('Queue is empty!')
        return
    await m.reply_text(text='Where do you want to upload the zip file?',
                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                           '📤 To Telegram', callback_data='zip_to_telegram')], [
                           InlineKeyboardButton('⛔ Cancel ⛔', callback_data='cancel')]]),
                       quote=True)


async def hardsub_handler(c: Client, m: Message):
    user_id = m.from_user.id
    UserSettings(user_id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    if queueDB.get(user_id, None) is None or not queueDB.get(user_id).get(
            'videos', []) or not queueDB.get(user_id).get('subtitles', []):
        await m.reply_text(
            'Queue must contain at least one video and one subtitle!')
        return
    await m.reply_text(text='Where do you want to upload the hardsubbed video?', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📤 To Telegram',
                                                                                                                                          callback_data='hardsub_to_telegram')], [InlineKeyboardButton(
                                                                                                                                              '⛔ Cancel ⛔', callback_data='cancel')]]), quote=True)


async def merge_handler(c: Client, m: Message):
    user_id = m.from_user.id
    UserSettings(user_id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    if queueDB.get(user_id, None) is None or not queueDB.get(user_id).get(
            'videos', []):
        await m.reply_text('Queue is empty!')
        return
    await m.reply_text(text='Where do you want to upload?', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('📤 To Telegram',
                                                                                                                     callback_data='to_telegram')], [InlineKeyboardButton('⛔ Cancel ⛔',
                                                                                                                                                                          callback_data='cancel')]]), quote=True)


async def encode_handler(c: Client, m: Message):
    user_id = m.from_user.id
    user = UserSettings(user_id, m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    if (m.reply_to_message is None or m.reply_to_message.video is None and
            m.reply_to_message.document is None):
        await m.reply_text('Reply to a video file with /encode')
        return
    media = m.reply_to_message.video or m.reply_to_message.document
    if media.file_name is None:
        await m.reply_text('File name not found')
        return
    currentFileNameExt = media.file_name.rsplit(sep='.')[-1].lower(
    ) if media.file_name else None
    if not currentFileNameExt or currentFileNameExt not in VIDEO_EXTENSIONS:
        await m.reply_text('This Video Format not Allowed for encoding!')
        return
    status_msg = await m.reply_text('📥 Downloading video...')
    download_dir = f'downloads/{str(user_id)}/'
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    file_dl_path = None
    try:
        c_time = time.time()
        prog = Progress(user_id, c, status_msg)
        file_dl_path = await c.download_media(message=media, file_name=f'{download_dir}{media.file_name}', progress=prog.
                                              progress_for_pyrogram, progress_args=(
            f'🚀 Downloading: `{media.file_name}`', c_time, '\n**Downloading**')
        )
    except Exception as e:
        await status_msg.edit(f'Failed to download Error: {e}')
        return
    if not file_dl_path:
        await status_msg.edit('Download failed!')
        return
    encoded_file_path = f'{download_dir}encoded_{media.file_name}'
    if not encoded_file_path.endswith('.mp4'):
        encoded_file_path = encoded_file_path.rsplit(sep='.')[0] + '.mp4'
    await status_msg.edit('⚙️ Encoding video...\n(This might take a while)')
    settings = getEncodeSettings(user_id)
    success = await encode_video(file_dl_path, encoded_file_path, **settings)
    if not success:
        await status_msg.edit('❌ Encoding failed!')
        await delete_all(root=download_dir)
        return
    await status_msg.edit('📤 Uploading encoded video...')
    try:
        duration = 1
        try:
            metadata = extractMetadata(createParser(encoded_file_path))
            if metadata.has('duration'):
                duration = metadata.get('duration').seconds
        except Exception:
            pass
        video_thumbnail = f'{download_dir}thumb.jpg'
        if user.thumbnail:
            await c.download_media(message=str(user.thumbnail), file_name=video_thumbnail)
        else:
            video_thumbnail = await take_screen_shot(encoded_file_path,
                                                     f'downloads/{str(user_id)}', duration / 2)
        width = 1280
        height = 720
        try:
            thumb = extractMetadata(createParser(video_thumbnail))
            if thumb and thumb.has('height'):
                height = thumb.get('height')
                width = thumb.get('width')
            img = Image.open(video_thumbnail)
            if width > height:
                img.resize((320, height))
            elif height > width:
                img.resize((width, 320))
            img.save(video_thumbnail)
            Image.open(video_thumbnail).convert('RGB').save(video_thumbnail,
                                                            'JPEG')
        except Exception as e:
            LOGGER.warning(f'Thumbnail error: {e}')
            video_thumbnail = None

        class FakeCb:

            def __init__(self, from_user, message):
                self.from_user = from_user
                self.message = message
        fake_cb = FakeCb(m.from_user, status_msg)
        await uploadVideo(c=c, cb=fake_cb, merged_video_path=encoded_file_path, width=width, height=height, duration=duration, video_thumbnail=video_thumbnail, file_size=os.path.
                          getsize(encoded_file_path), upload_mode=UPLOAD_AS_DOC.get(
                              f'{user_id}', False))
    except Exception as e:
        await status_msg.edit(f'Upload failed: {e}')
        LOGGER.error(f'Upload error: {e}')
    await status_msg.delete()
    await delete_all(root=download_dir)


async def media_extracter(c: Client, m: Message):
    user = UserSettings(uid=m.from_user.id, name=m.from_user.first_name)
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(text=f"""Hi **{m.from_user.first_name}**

 🛡️ Unfortunately you can't use me

**Contact: 🈲 @{Config.OWNER_USERNAME}** """, quote=True)
        return
    if user.merge_mode == 4:
        if m.reply_to_message is None:
            await m.reply(text='Reply /extract to a video or document file')
            return
        rmess = m.reply_to_message
        if rmess.video or rmess.document:
            media = rmess.video or rmess.document
            mid = rmess.id
            file_name = media.file_name
            if file_name is None:
                await m.reply('File name not found; goto @yashoswalyo')
                return
            markup = bMaker.makebuttons(
                set1=[
                    'Video',
                    'Audio',
                    'Subtitle',
                    'Cancel'],
                set2=[
                    f'extract_video_{mid}',
                    f'extract_audio_{mid}',
                    f'extract_subtitle_{mid}',
                    'cancel'],
                isCallback=True,
                rows=2)
            await m.reply(text='Choose from below what you want to extract?', quote=True,
                          reply_markup=InlineKeyboardMarkup(markup))
    else:
        await m.reply(text='Change settings and set mode to extract\nthen use /extract command'
                      )


async def about_handler(c: Client, m: Message):
    await m.reply_text(text="""
**ᴡʜᴀᴛ's ɴᴇᴡ:**
👨‍💻 ʙᴀɴ/ᴜɴʙᴀɴ ᴜsᴇʀs
👨‍💻 ᴇxᴛʀᴀᴄᴛ ᴀʟʟ ᴀᴜᴅɪᴏs ᴀɴᴅ sᴜʙᴛɪᴛʟᴇs ғʀᴏᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴍᴇᴅɪᴀ
👨‍💻 ᴍᴇʀɢᴇ ᴠɪᴅᴇᴏ + ᴀᴜᴅɪᴏ
👨‍💻 ᴍᴇʀɢᴇ ᴠɪᴅᴇᴏ + sᴜʙᴛɪᴛʟᴇs
👨‍💻 ᴜᴘʟᴏᴀᴅ ᴛᴏ ᴅʀɪᴠᴇ ᴜsɪɴɢ ʏᴏᴜʀ ᴏᴡɴ ʀᴄʟᴏɴᴇ ᴄᴏɴғɪɢ
👨‍💻 ᴍᴇʀɢᴇᴅ ᴠɪᴅᴇᴏ ᴘʀᴇsᴇʀᴠᴇs ᴀʟʟ sᴛʀᴇᴀᴍs ᴏғ ᴛʜᴇ ғɪʀsᴛ ᴠɪᴅᴇᴏ ʏᴏᴜ sᴇɴᴅ (ɪ.ᴇ ᴀʟʟ ᴀᴜᴅɪᴏᴛʀᴀᴄᴋs/sᴜʙᴛɪᴛʟᴇs)
➖➖➖➖➖➖➖➖➖➖➖➖➖
**ғᴇᴀᴛᴜʀᴇs**
🔰 ᴍᴇʀɢᴇ ᴜᴘᴛᴏ 𝟷𝟶 ᴠɪᴅᴇᴏ ɪɴ ᴏɴᴇ
🔰 ᴜᴘʟᴏᴀᴅ ᴀs ᴅᴏᴄᴜᴍᴇɴᴛs/ᴠɪᴅᴇᴏ
🔰 ᴄᴜsᴛᴏᴍs ᴛʜᴜᴍʙɴᴀɪʟ sᴜᴘᴘᴏʀᴛ
🔰 ᴜsᴇʀs ᴄᴀɴ ʟᴏɢɪɴ ᴛᴏ ʙᴏᴛ ᴜsɪɴɢ ᴘᴀssᴡᴏʀᴅ
🔰 ᴏᴡɴᴇʀ ᴄᴀɴ ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs
        """, quote=True, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton('👨\u200d💻Developer👨\u200d💻', url='https://t.me/yashoswalyo')], [InlineKeyboardButton('🏘Source Code🏘',
                                                                                                                  url='https://github.com/yashoswalyo/MERGE-BOT'),
                                                                                             InlineKeyboardButton('🤔Deployed By🤔', url=f'https://t.me/{Config.OWNER_USERNAME}')], [InlineKeyboardButton(
                                                                                                 'Close 🔐', callback_data='close')]]))


async def save_thumbnail(c: Client, m: Message):
    if m.reply_to_message:
        if m.reply_to_message.photo:
            await photo_handler(c, m.reply_to_message)
        else:
            await m.reply(text='Please reply to a valid photo')
    else:
        await m.reply(text='Please reply to a message')
    return


async def show_thumbnail(c: Client, m: Message):
    try:
        user = UserSettings(m.from_user.id, m.from_user.first_name)
        thumb_id = user.thumbnail
        LOCATION = f'downloads/{str(m.from_user.id)}_thumb.jpg'
        if os.path.exists(LOCATION):
            await m.reply_photo(photo=LOCATION, caption='🖼️ Your custom thumbnail', quote=True)
        elif thumb_id is not None:
            await c.download_media(message=str(thumb_id), file_name=LOCATION)
            await m.reply_photo(photo=LOCATION, caption='🖼️ Your custom thumbnail', quote=True)
        else:
            await m.reply_text(text='❌ Custom thumbnail not found', quote=True)
        del user
    except Exception as err:
        LOGGER.info(err)
        await m.reply_text(text='❌ Custom thumbnail not found', quote=True)


async def delete_thumbnail(c: Client, m: Message):
    try:
        user = UserSettings(m.from_user.id, m.from_user.first_name)
        user.thumbnail = None
        user.set()
        if os.path.exists(f'downloads/{str(m.from_user.id)}'):
            os.remove(f'downloads/{str(m.from_user.id)}')
            await m.reply_text('✅ Deleted Sucessfully', quote=True)
            del user
        else:
            raise Exception('Thumbnail file not found')
    except Exception:
        await m.reply_text(text='❌ Custom thumbnail not found', quote=True)


async def ban_user(c: Client, m: Message):
    incoming = m.text.split(' ')[0]
    if incoming == '/ban':
        if m.from_user.id == int(Config.OWNER):
            try:
                abuser_id = int(m.text.split(' ')[1])
                if abuser_id == int(Config.OWNER):
                    await m.reply_text(
                        "I can't ban you master,\nPlease don't abandon me. ",
                        quote=True)
                else:
                    try:
                        user_obj: User = await c.get_users(abuser_id)
                        udata = UserSettings(uid=abuser_id, name=user_obj.
                                             first_name)
                        udata.banned = True
                        udata.allowed = False
                        udata.set()
                        await m.reply_text(
                            f'Pooof, {user_obj.first_name} has been **BANNED**', quote=True)
                        acknowledgement = f"""
Dear {user_obj.first_name},
I found your messages annoying and forwarded them to our team of moderators for inspection. The moderators have confirmed the report and your account is now banned.

While the account is banned, you will not be able to do certain things, like merging videos/audios/subtitles or extract audios from Telegram media.

Your account can be released only by @{Config.OWNER_USERNAME}."""
                        try:
                            await c.send_message(chat_id=abuser_id, text=acknowledgement)
                        except Exception as e:
                            await m.reply_text(
                                f"""An error occured while sending acknowledgement

`{e}`""", quote=True)
                            LOGGER.error(e)
                    except Exception as e:
                        LOGGER.error(e)
            except BaseException:
                await m.reply_text(
                    """**Command:**
  `/ban <user_id>`

**Usage:**
  `user_id`: User ID of the user""", quote=True, parse_mode=enums.parse_mode.ParseMode.
                    MARKDOWN)
        else:
            await m.reply_text(
                """**(Only for __OWNER__)
Command:**
  `/ban <user_id>`

**Usage:**
  `user_id`: User ID of the user""", quote=True, parse_mode=enums.parse_mode.ParseMode.MARKDOWN)
        return
    elif incoming == '/unban':
        if m.from_user.id == int(Config.OWNER):
            try:
                abuser_id = int(m.text.split(' ')[1])
                if abuser_id == int(Config.OWNER):
                    await m.reply_text(
                        "I can't ban you master,\nPlease don't abandon me. ",
                        quote=True)
                else:
                    try:
                        user_obj: User = await c.get_users(abuser_id)
                        udata = UserSettings(uid=abuser_id, name=user_obj.
                                             first_name)
                        udata.banned = False
                        udata.allowed = True
                        udata.set()
                        await m.reply_text(
                            f'Pooof, {user_obj.first_name} has been **UN_BANNED**', quote=True)
                        release_notice = f"""
Good news {user_obj.first_name}, the ban has been uplifted on your account. You're free as a bird!"""
                        try:
                            await c.send_message(chat_id=abuser_id, text=release_notice)
                        except Exception as e:
                            await m.reply_text(
                                f"""An error occured while sending release notice

`{e}`""", quote=True)
                            LOGGER.error(e)
                    except Exception as e:
                        LOGGER.error(e)
            except BaseException:
                await m.reply_text(
                    """**Command:**
  `/unban <user_id>`

**Usage:**
  `user_id`: User ID of the user""", quote=True, parse_mode=enums.parse_mode.ParseMode.
                    MARKDOWN)
        else:
            await m.reply_text(
                """**(Only for __OWNER__)
Command:**
  `/unban <user_id>`

**Usage:**
  `user_id`: User ID of the user""", quote=True, parse_mode=enums.parse_mode.ParseMode.MARKDOWN)
        return


async def showQueue(c: Client, cb: CallbackQuery):
    try:
        markup = await makeButtons(c, cb.message, queueDB)
        await cb.message.edit(text='Okay,\nNow Send Me Next Video or Press **Merge Now** Button!',
                              reply_markup=InlineKeyboardMarkup(markup))
    except ValueError:
        await cb.message.edit('Send Some more videos')
    return


async def delete_all(root):
    try:
        shutil.rmtree(root)
    except Exception as e:
        LOGGER.info(e)


async def makeButtons(bot: Client, m: Message, db: dict):
    markup = []
    user = UserSettings(m.chat.id, m.chat.first_name)
    if user.merge_mode == 1:
        for i in (await bot.get_messages(chat_id=m.chat.id, message_ids=db.
                                         get(m.chat.id)['videos'])):
            media = i.video or i.document or None
            if media is None:
                continue
            else:
                markup.append([InlineKeyboardButton(
                    f'{media.file_name}', callback_data=f'showFileName_{i.id}')])
    elif user.merge_mode == 2:
        msgs: list[Message] = await bot.get_messages(chat_id=m.chat.id,
                                                     message_ids=db.get(m.chat.id)['audios'])
        msgs.insert(0, await bot.get_messages(chat_id=m.chat.id,
                                              message_ids=db.get(m.chat.id)['videos'][0]))
        for i in msgs:
            media = i.audio or i.document or i.video or None
            if media is None:
                continue
            else:
                markup.append([InlineKeyboardButton(
                    f'{media.file_name}', callback_data='tryotherbutton')])
    elif user.merge_mode == 3:
        msgs: list[Message] = await bot.get_messages(chat_id=m.chat.id,
                                                     message_ids=db.get(m.chat.id)['subtitles'])
        msgs.insert(0, await bot.get_messages(chat_id=m.chat.id,
                                              message_ids=db.get(m.chat.id)['videos'][0]))
        for i in msgs:
            media = i.video or i.document or None
            if media is None:
                continue
            else:
                markup.append([InlineKeyboardButton(
                    f'{media.file_name}', callback_data='tryotherbutton')])
    markup.append([InlineKeyboardButton('🔗 Merge Now', callback_data='merge')])
    markup.append([InlineKeyboardButton(
        '💥 Clear Files', callback_data='cancel')])
    return markup


LOGCHANNEL = Config.LOGCHANNEL
userBot = None
if __name__ == '__main__':

    async def root_route_handler(request):
        return web.json_response({'status': 'running'})

    async def main():
        global userBot
        try:
            if Config.USER_SESSION_STRING is None:
                raise KeyError
            LOGGER.info('Starting USER Session')
            userBot = Client(name='merge-bot-user', session_string=Config.
                             USER_SESSION_STRING, no_updates=True)
        except KeyError:
            userBot = None
            LOGGER.warning('No User Session, Default Bot session will be used')
        if userBot is not None:
            try:
                async with userBot:
                    await userBot.send_message(chat_id=int(LOGCHANNEL),
                                               text="""Bot booted with Premium Account,

  Thanks for using <a href='https://github.com/yashoswalyo/merge-bot'>this repo</a>""", disable_web_page_preview=True)
                    user = await userBot.get_me()
                    Config.IS_PREMIUM = user.is_premium
            except Exception as err:
                LOGGER.error(f'{err}')
                Config.IS_PREMIUM = False
        else:
            Config.IS_PREMIUM = False
        mergeApp = MergeBot(
            name='merge-bot',
            api_hash=Config.API_HASH,
            api_id=int(
                Config.TELEGRAM_API),
            bot_token=Config.BOT_TOKEN,
            workers=300,
            plugins=dict(
                root='Vivian'),
            app_version='5.0+yash-mergebot',
            max_concurrent_transmissions=6)
        mergeApp.add_handler(MessageHandler(sendLogFile, filters.command([
            'log'])))
        mergeApp.add_handler(MessageHandler(stats_handler, filters.command(
            ['stats'])))
        mergeApp.add_handler(
            MessageHandler(
                broadcast_handler,
                filters. command(
                    ['broadcast']) & filters.user(
                    Config.OWNER_USERNAME)))
        mergeApp.add_handler(
            MessageHandler(
                files_handler,
                (filters. document | filters.video | filters.audio) & filters.private))
        mergeApp.add_handler(MessageHandler(photo_handler, filters.photo &
                                            filters.private))
        mergeApp.add_handler(MessageHandler(zip_handler, filters.command([
            'zip'])))
        mergeApp.add_handler(MessageHandler(hardsub_handler, filters.
                                            command(['hardsub'])))
        mergeApp.add_handler(MessageHandler(merge_handler, filters.command(
            ['merge'])))
        mergeApp.add_handler(MessageHandler(encode_handler, filters.command
                                            (['encode'])))
        mergeApp.add_handler(MessageHandler(media_extracter, filters.
                                            command(['extract'])))
        mergeApp.add_handler(MessageHandler(about_handler, filters.command(
            ['about'])))
        mergeApp.add_handler(MessageHandler(save_thumbnail, filters.command(
            ['savethumb', 'setthumb', 'savethumbnail'])))
        mergeApp.add_handler(MessageHandler(show_thumbnail, filters.command
                                            (['showthumbnail'])))
        mergeApp.add_handler(MessageHandler(delete_thumbnail, filters.
                                            command(['deletethumbnail'])))
        mergeApp.add_handler(MessageHandler(ban_user, filters.command([
            'ban', 'unban'])))
        app = web.Application()
        app.router.add_get('/', root_route_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
        await site.start()
        LOGGER.info(f'Web server started on port {Config.PORT}')
        await mergeApp.start()
        LOGGER.info('Bot started')
        await pyrogram.idle()
        await mergeApp.stop()
        await runner.cleanup()
    import pyrogram
    asyncio.run(main())

_ = listen
