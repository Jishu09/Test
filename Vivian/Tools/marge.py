import asyncio
import os
import time

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image
from pyrogram import Client
from pyrogram.errors import MessageNotModified
from pyrogram.errors.rpc_error import UnknownError
from pyrogram.types import CallbackQuery, Message

from bot import delete_all
from config import Config
from main import (AUDIO_EXTENSIONS, LOGGER, SUBTITLE_EXTENSIONS, UPLOAD_AS_DOC,
                  VIDEO_EXTENSIONS, formatDB, gDict, queueDB)
from Vivian.Function.ffmpeg import (MergeAudio, MergeSub, MergeSubNew,
                                    MergeVideo, take_screen_shot)
from Vivian.Function.utils import UserSettings
from Vivian.Tools.display_progress import Progress
from Vivian.Tools.uploader import uploadVideo


async def mergeNow(c: Client, cb: CallbackQuery, new_file_name: str):
    cb.message.reply_to_message

    vid_list = list()
    sIndex = 0
    await cb.message.edit("⭕ Processing...")
    duration = 0
    list_message_ids = queueDB.get(cb.from_user.id)["videos"]
    list_subtitle_ids = queueDB.get(cb.from_user.id)["subtitles"]

    LOGGER.info(Config.IS_PREMIUM)
    LOGGER.info(f"Videos: {list_message_ids}")
    LOGGER.info(f"Subs: {list_subtitle_ids}")
    if list_message_ids is None:
        await cb.answer("Queue Empty", show_alert=True)
        await cb.message.delete(True)
        return
    if not os.path.exists(f"downloads/{str(cb.from_user.id)}/"):
        os.makedirs(f"downloads/{str(cb.from_user.id)}/")
    input_ = f"downloads/{str(cb.from_user.id)}/input.txt"
    all = len(list_message_ids)
    n = 1

    msgs = await c.get_messages(chat_id=cb.from_user.id, message_ids=list_message_ids)
    msgs.sort(key=lambda x: list_message_ids.index(x.id))

    for i in msgs:
        media = i.video or i.document
        await cb.message.edit(f"📥 Starting Download of ... `{media.file_name}`")
        LOGGER.info(f"📥 Starting Download of ... {media.file_name}")
        await asyncio.sleep(5)
        file_dl_path = None
        sub_dl_path = None
        try:
            c_time = time.time()
            prog = Progress(cb.from_user.id, c, cb.message)
            file_dl_path = await c.download_media(
                message=media,
                file_name=f"downloads/{str(cb.from_user.id)}/{str(i.id)}/vid.mkv",
                progress=prog.progress_for_pyrogram,
                progress_args=(f"🚀 Downloading: `{media.file_name}`", c_time, f"\n**Downloading: {n}/{all}**"),
            )
            n += 1
            if gDict[cb.message.chat.id] and cb.message.id in gDict[cb.message.chat.id]:
                return
            await cb.message.edit(f"Downloaded Sucessfully ... `{media.file_name}`")
            LOGGER.info(f"Downloaded Sucessfully ... {media.file_name}")
            await asyncio.sleep(5)
        except UnknownError as e:
            LOGGER.info(e)
        except Exception as downloadErr:
            LOGGER.info(f"Failed to download Error: {downloadErr}")
            queueDB.get(cb.from_user.id)["video"].remove(i.id)
            await cb.message.edit("❗File Skipped!")
            await asyncio.sleep(4)
            continue

        if list_subtitle_ids[sIndex] is not None:
            a = await c.get_messages(
                chat_id=cb.from_user.id, message_ids=list_subtitle_ids[sIndex]
            )
            sub_dl_path = await c.download_media(
                message=a,
                file_name=f"downloads/{str(cb.from_user.id)}/{str(a.id)}/",
            )
            LOGGER.info("Got sub: ", a.document.file_name)
            file_dl_path = await MergeSub(file_dl_path, sub_dl_path, cb.from_user.id)
            LOGGER.info("Added subs")
        sIndex += 1

        metadata = extractMetadata(createParser(file_dl_path))
        try:
            if metadata.has("duration"):
                duration += metadata.get("duration").seconds
            vid_list.append(f"file '{file_dl_path}'")
        except BaseException:
            await delete_all(root=f"downloads/{str(cb.from_user.id)}")
            queueDB.update(
                {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}}
            )
            formatDB.update({cb.from_user.id: None})
            await cb.message.edit("⚠️ Video is corrupted")
            return

    _cache = list()
    for i in range(len(vid_list)):
        if vid_list[i] not in _cache:
            _cache.append(vid_list[i])
    vid_list = _cache
    LOGGER.info(f"Trying to merge videos user {cb.from_user.id}")
    await cb.message.edit("🔀 Trying to merge videos ...")
    with open(input_, "w") as _list:
        _list.write("\n".join(vid_list))
    merged_video_path = await MergeVideo(
        input_file=input_, user_id=cb.from_user.id, message=cb.message, format_="mkv"
    )
    if merged_video_path is None:
        await cb.message.edit("❌ Failed to merge video !")
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    try:
        await cb.message.edit("✅ Sucessfully Merged Video !")
    except MessageNotModified:
        await cb.message.edit("Sucessfully Merged Video ! ✅")
    LOGGER.info(f"Video merged for: {cb.from_user.first_name} ")
    await asyncio.sleep(3)
    file_size = os.path.getsize(merged_video_path)
    os.rename(merged_video_path, new_file_name)
    await cb.message.edit(
        f"🔄 Renamed Merged Video to\n **{new_file_name.rsplit('/', 1)[-1]}**"
    )
    await asyncio.sleep(3)
    merged_video_path = new_file_name
    if file_size > 2044723200 and Config.IS_PREMIUM is False:
        await cb.message.edit(
            f"Video is Larger than 2GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to add premium account to get 4GB TG uploads"
        )
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    if Config.IS_PREMIUM and file_size > 4241280205:
        await cb.message.edit(
            f"Video is Larger than 4GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to die with premium account"
        )
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    await cb.message.edit("🎥 Extracting Video Data ...")
    duration = 1
    try:
        metadata = extractMetadata(createParser(merged_video_path))
        if metadata.has("duration"):
            duration = metadata.get("duration").seconds
    except Exception:
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit("⭕ Merged Video is corrupted")
        return
    try:
        user = UserSettings(cb.from_user.id, cb.from_user.first_name)
        thumb_id = user.thumbnail
        if thumb_id is None:
            raise Exception

        video_thumbnail = f"downloads/{str(cb.from_user.id)}_thumb.jpg"
        await c.download_media(message=str(thumb_id), file_name=video_thumbnail)
    except Exception:
        LOGGER.info("Generating thumb")
        video_thumbnail = await take_screen_shot(
            merged_video_path, f"downloads/{str(cb.from_user.id)}", (duration / 2)
        )
    width = 1280
    height = 720
    try:
        thumb = extractMetadata(createParser(video_thumbnail))
        height = thumb.get("height")
        width = thumb.get("width")
        img = Image.open(video_thumbnail)
        if width > height:
            img.resize((320, height))
        elif height > width:
            img.resize((width, 320))
        img.save(video_thumbnail)
        Image.open(video_thumbnail).convert(
            "RGB").save(video_thumbnail, "JPEG")
    except BaseException:
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit("⭕ Merged Video is corrupted")
        return
    await uploadVideo(
        c=c,
        cb=cb,
        merged_video_path=merged_video_path,
        width=width,
        height=height,
        duration=duration,
        video_thumbnail=video_thumbnail,
        file_size=os.path.getsize(merged_video_path),
        upload_mode=UPLOAD_AS_DOC.get(f"{cb.from_user.id}", False),
    )
    await cb.message.delete(True)
    await delete_all(root=f"downloads/{str(cb.from_user.id)}")
    queueDB.update(
        {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
    formatDB.update({cb.from_user.id: None})
    return


async def mergeAudio(c: Client, cb: CallbackQuery, new_file_name: str):
    cb.message.reply_to_message
    files_list = []
    await cb.message.edit("⭕ Processing...")
    duration = 0
    video_mess = queueDB.get(cb.from_user.id)["videos"][0]
    list_message_ids: list = queueDB.get(cb.from_user.id)["audios"]
    list_message_ids.insert(0, video_mess)
    if list_message_ids is None:
        await cb.answer("Queue Empty", show_alert=True)
        await cb.message.delete(True)
        return
    if not os.path.exists(f"downloads/{str(cb.from_user.id)}/"):
        os.makedirs(f"downloads/{str(cb.from_user.id)}/")
    all = len(list_message_ids)
    n = 1
    msgs: list[Message] = await c.get_messages(
        chat_id=cb.from_user.id, message_ids=list_message_ids
    )
    msgs.sort(key=lambda x: list_message_ids.index(x.id))
    for i in msgs:
        media = i.video or i.document or i.audio
        await cb.message.edit(f"📥 Starting Download of ... `{media.file_name}`")
        LOGGER.info(f"📥 Starting Download of ... {media.file_name}")
        currentFileNameExt = media.file_name.rsplit(sep=".")[-1].lower()
        if currentFileNameExt in VIDEO_EXTENSIONS:
            tmpFileName = "vid.mkv"
        elif currentFileNameExt in AUDIO_EXTENSIONS:
            tmpFileName = "audio." + currentFileNameExt
        await asyncio.sleep(5)
        file_dl_path = None
        try:
            c_time = time.time()
            prog = Progress(cb.from_user.id, c, cb.message)
            file_dl_path = await c.download_media(
                message=media,
                file_name=f"downloads/{str(cb.from_user.id)}/{str(i.id)}/{tmpFileName}",
                progress=prog.progress_for_pyrogram,
                progress_args=(f"🚀 Downloading: `{media.file_name}`", c_time, f"\n**Downloading: {n}/{all}**"),
            )
            n += 1
            if gDict[cb.message.chat.id] and cb.message.id in gDict[cb.message.chat.id]:
                return
            await cb.message.edit(f"Downloaded Sucessfully ... `{media.file_name}`")
            LOGGER.info(f"Downloaded Sucessfully ... {media.file_name}")
            await asyncio.sleep(4)
        except Exception as downloadErr:
            LOGGER.warning(f"Failed to download Error: {downloadErr}")
            queueDB.get(cb.from_user.id)["audios"].remove(i.id)
            await cb.message.edit("❗File Skipped!")
            await asyncio.sleep(4)
            await cb.message.delete(True)
            continue
        files_list.append(f"{file_dl_path}")

    muxed_video = await MergeAudio(files_list[0], files_list, cb.from_user.id)
    if muxed_video is None:
        await cb.message.edit("❌ Failed to add audio to video !")
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    try:
        await cb.message.edit("✅ Sucessfully Muxed Video !")
    except MessageNotModified:
        await cb.message.edit("Sucessfully Muxed Video ! ✅")
    LOGGER.info(f"Video muxed for: {cb.from_user.first_name} ")
    await asyncio.sleep(3)
    file_size = os.path.getsize(muxed_video)
    os.rename(muxed_video, new_file_name)
    await cb.message.edit(
        f"🔄 Renaming Video to\n **{new_file_name.rsplit('/', 1)[-1]}**"
    )
    await asyncio.sleep(4)
    merged_video_path = new_file_name

    if file_size > 2044723200 and Config.IS_PREMIUM is False:
        await cb.message.edit(
            f"Video is Larger than 2GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to add premium account to get 4GB TG uploads"
        )
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    if Config.IS_PREMIUM and file_size > 4241280205:
        await cb.message.edit(
            f"Video is Larger than 4GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to die with premium account"
        )
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    await cb.message.edit("🎥 Extracting Video Data ...")

    duration = 1
    try:
        metadata = extractMetadata(createParser(merged_video_path))
        if metadata.has("duration"):
            duration = metadata.get("duration").seconds
    except Exception:
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit("⭕ Merged Video is corrupted")
        return
    try:
        user = UserSettings(cb.from_user.id, cb.from_user.first_name)
        thumb_id = user.thumbnail
        if thumb_id is None:
            raise Exception
        video_thumbnail = f"downloads/{str(cb.from_user.id)}_thumb.jpg"
        await c.download_media(message=str(thumb_id), file_name=video_thumbnail)
    except Exception:
        LOGGER.info("Generating thumb")
        video_thumbnail = await take_screen_shot(
            merged_video_path, f"downloads/{str(cb.from_user.id)}", (duration / 2)
        )
    width = 1280
    height = 720
    try:
        thumb = extractMetadata(createParser(video_thumbnail))
        height = thumb.get("height")
        width = thumb.get("width")
        img = Image.open(video_thumbnail)
        if width > height:
            img.resize((320, height))
        elif height > width:
            img.resize((width, 320))
        img.save(video_thumbnail)
        Image.open(video_thumbnail).convert(
            "RGB").save(video_thumbnail, "JPEG")
    except BaseException:
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit(
            "⭕ Merged Video is corrupted \n\n<i>Try setting custom thumbnail</i>",
        )
        return
    await uploadVideo(
        c=c,
        cb=cb,
        merged_video_path=merged_video_path,
        width=width,
        height=height,
        duration=duration,
        video_thumbnail=video_thumbnail,
        file_size=os.path.getsize(merged_video_path),
        upload_mode=UPLOAD_AS_DOC.get(f"{cb.from_user.id}", False),
    )
    await cb.message.delete(True)
    await delete_all(root=f"downloads/{str(cb.from_user.id)}")
    queueDB.update(
        {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
    formatDB.update({cb.from_user.id: None})
    return


async def mergeSub(c: Client, cb: CallbackQuery, new_file_name: str):
    cb.message.reply_to_message
    vid_list = list()
    await cb.message.edit("⭕ Processing...")
    duration = 0
    video_mess = queueDB.get(cb.from_user.id)["videos"][0]
    list_message_ids: list = queueDB.get(cb.from_user.id)["subtitles"]
    list_message_ids.insert(0, video_mess)
    if list_message_ids is None:
        await cb.answer("Queue Empty", show_alert=True)
        await cb.message.delete(True)
        return
    if not os.path.exists(f"downloads/{str(cb.from_user.id)}/"):
        os.makedirs(f"downloads/{str(cb.from_user.id)}/")
    msgs: list[Message] = await c.get_messages(
        chat_id=cb.from_user.id, message_ids=list_message_ids
    )
    msgs.sort(key=lambda x: list_message_ids.index(x.id))
    all = len(msgs)
    n = 1
    for i in msgs:
        media = i.video or i.document
        await cb.message.edit(f"📥 Starting Download of ... `{media.file_name}`")
        LOGGER.info(f"📥 Starting Download of ... {media.file_name}")
        currentFileNameExt = media.file_name.rsplit(sep=".")[-1].lower()
        if currentFileNameExt in VIDEO_EXTENSIONS:
            tmpFileName = "vid.mkv"
        elif currentFileNameExt in SUBTITLE_EXTENSIONS:
            tmpFileName = "sub." + currentFileNameExt
        await asyncio.sleep(5)
        file_dl_path = None
        try:
            c_time = time.time()
            prog = Progress(cb.from_user.id, c, cb.message)
            file_dl_path = await c.download_media(
                message=media,
                file_name=f"downloads/{str(cb.from_user.id)}/{str(i.id)}/{tmpFileName}",
                progress=prog.progress_for_pyrogram,
                progress_args=(f"🚀 Downloading: `{media.file_name}`", c_time, f"\n**Downloading: {n}/{all}**"),
            )
            n += 1
            if gDict[cb.message.chat.id] and cb.message.id in gDict[cb.message.chat.id]:
                return
            await cb.message.edit(f"Downloaded Sucessfully ... `{media.file_name}`")
            LOGGER.info(f"Downloaded Sucessfully ... {media.file_name}")
            await asyncio.sleep(5)
        except Exception as downloadErr:
            LOGGER.warning(f"Failed to download Error: {downloadErr}")
            queueDB.get(cb.from_user.id)["subtitles"].remove(i.id)
            await cb.message.edit("❗File Skipped!")
            await asyncio.sleep(4)
            await cb.message.delete(True)
            continue
        vid_list.append(f"{file_dl_path}")

    subbed_video = await MergeSubNew(
        filePath=vid_list[0],
        subPath=vid_list[1],
        user_id=cb.from_user.id,
        file_list=vid_list,
    )
    if subbed_video is None:
        await cb.message.edit("❌ Failed to add subs video !")
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    try:
        await cb.message.edit("✅ Sucessfully Muxed Video !")
    except MessageNotModified:
        await cb.message.edit("Sucessfully Muxed Video ! ✅")
    LOGGER.info(f"Video muxed for: {cb.from_user.first_name} ")
    await asyncio.sleep(3)
    file_size = os.path.getsize(subbed_video)
    os.rename(subbed_video, new_file_name)
    await cb.message.edit(
        f"🔄 Renaming Video to\n **{new_file_name.rsplit('/', 1)[-1]}**"
    )
    await asyncio.sleep(3)
    merged_video_path = new_file_name
    if file_size > 2044723200 and Config.IS_PREMIUM is False:
        await cb.message.edit(
            f"Video is Larger than 2GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to add premium account to get 4GB TG uploads"
        )
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    if Config.IS_PREMIUM and file_size > 4241280205:
        await cb.message.edit(
            f"Video is Larger than 4GB Can't Upload,\n\n Tell {Config.OWNER_USERNAME} to die with premium account"
        )
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return
    await cb.message.edit("🎥 Extracting Video Data ...")

    duration = 1
    try:
        metadata = extractMetadata(createParser(merged_video_path))
        if metadata.has("duration"):
            duration = metadata.get("duration").seconds
    except Exception:
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit("⭕ Merged Video is corrupted")
        return
    try:
        user = UserSettings(cb.from_user.id, cb.from_user.first_name)
        thumb_id = user.thumbnail
        if thumb_id is None:
            raise Exception

        video_thumbnail = f"downloads/{str(cb.from_user.id)}_thumb.jpg"
        await c.download_media(message=str(thumb_id), file_name=video_thumbnail)
    except Exception:
        LOGGER.info("Generating thumb")
        video_thumbnail = await take_screen_shot(
            merged_video_path, f"downloads/{str(cb.from_user.id)}", (duration / 2)
        )
    width = 1280
    height = 720
    try:
        thumb = extractMetadata(createParser(video_thumbnail))
        height = thumb.get("height")
        width = thumb.get("width")
        img = Image.open(video_thumbnail)
        if width > height:
            img.resize((320, height))
        elif height > width:
            img.resize((width, 320))
        img.save(video_thumbnail)
        Image.open(video_thumbnail).convert(
            "RGB").save(video_thumbnail, "JPEG")
    except BaseException:
        await delete_all(root=f"downloads/{str(cb.from_user.id)}")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit(
            "⭕ Merged Video is corrupted \n\n<i>Try setting custom thumbnail</i>",
        )
        return
    await uploadVideo(
        c=c,
        cb=cb,
        merged_video_path=merged_video_path,
        width=width,
        height=height,
        duration=duration,
        video_thumbnail=video_thumbnail,
        file_size=os.path.getsize(merged_video_path),
        upload_mode=UPLOAD_AS_DOC.get(f"{cb.from_user.id}", False),
    )
    await cb.message.delete(True)
    await delete_all(root=f"downloads/{str(cb.from_user.id)}")
    queueDB.update(
        {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
    formatDB.update({cb.from_user.id: None})
    return
