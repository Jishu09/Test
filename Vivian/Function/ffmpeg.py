import asyncio
import os
import shutil
import time

import ffmpeg
from pyrogram.types import Message

from main import LOGGER
from Vivian.Database.database import getMetadata, getUserMergeSettings
from Vivian.Function.utils import get_path_size


def generate_metadata_args(user_id):
    user_settings = getUserMergeSettings(user_id)
    args = []
    if user_settings and user_settings.get(
            "user_settings", {}).get(
            "edit_metadata", False):
        metadata = getMetadata(user_id)
        if metadata:
            mapping = {
                "title": "title",
                "author": "author",
                "artist": "artist",
                "audio": "audio",
                "subtitle": "subtitle",
                "video": "video",
                "encoded_by": "encoded_by",
                "custom_tag": "custom_tag",
                "comment": "comment",
                "dubbed_by": "dubbed_by",
                "channel": "channel",
                "website": "website",
                "copyright": "copyright",
                "publisher": "publisher",
                "encoder": "encoder",
                "source": "source",
                "studio": "studio",
                "official_site": "official_site"
            }
            for key, val in mapping.items():
                meta_val = metadata.get(key)
                if meta_val and meta_val != "Not set":
                    args.extend(["-metadata", f"{val}={meta_val}"])
    return args


async def MergeVideo(
        input_file: str,
        user_id: int,
        message: Message,
        format_: str):
    """
    This is for Merging Videos Together!
    :param `input_file`: input.txt file's location.
    :param `user_id`: Pass user_id as integer.
    :param `message`: Pass Editable Message for Showing FFmpeg Progress.
    :param `format_`: Pass File Extension.
    :return: This will return Merged Video File Path
    """
    output_vid = f"downloads/{str(user_id)}/[@yashoswalyo].{format_.lower()}"
    metadata_args = generate_metadata_args(user_id)
    file_generator_command = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        input_file,
        "-map",
        "0",
        *metadata_args,
        "-c",
        "copy",
        output_vid,
    ]
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *file_generator_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except NotImplementedError:
        await message.edit(
            text="Unable to Execute FFmpeg Command! Got `NotImplementedError` ...\n\nPlease run bot in a Linux/Unix Environment."
        )
        await asyncio.sleep(10)
        return None
    await message.edit("Merging Video Now ...\n\nPlease Keep Patience ...")
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    LOGGER.info(e_response)
    LOGGER.info(t_response)
    if os.path.lexists(output_vid):
        return output_vid
    else:
        return None


async def MergeSub(filePath: str, subPath: str, user_id):
    """
    This is for Merging Video + Subtitle Together.

    Parameters:
    - `filePath`: Path to Video file.
    - `subPath`: Path to subtitile file.
    - `user_id`: To get parent directory.

    returns: Merged Video File Path
    """
    LOGGER.info("Generating mux command")
    metadata_args = generate_metadata_args(user_id)
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    muxcmd.append("-i")
    muxcmd.append(filePath)
    muxcmd.append("-i")
    muxcmd.append(subPath)
    muxcmd.append("-map")
    muxcmd.append("0:v:0")
    muxcmd.append("-map")
    muxcmd.append("0:a:?")
    muxcmd.append("-map")
    muxcmd.append("0:s:?")
    muxcmd.append("-map")
    muxcmd.append("1:s")
    videoData = ffmpeg.probe(filename=filePath)
    videoStreamsData = videoData.get("streams")
    subTrack = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i]["codec_type"] == "subtitle":
            subTrack += 1
    muxcmd.append(f"-metadata:s:s:{subTrack}")
    subTrack += 1
    subTitle = f"Track {subTrack} - tg@yashoswalyo"
    muxcmd.append(f"title={subTitle}")
    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("srt")
    muxcmd.extend(metadata_args)
    muxcmd.append(
        f"./downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv")
    LOGGER.info("Muxing subtitles")
    process = await asyncio.create_subprocess_exec(
        *muxcmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    orgFilePath = shutil.move(
        f"downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv", filePath
    )
    return orgFilePath


async def MergeSubNew(filePath: str, subPath: str, user_id, file_list):
    metadata_args = generate_metadata_args(user_id)
    """
    This method is for Merging Video + Subtitle(s) Together.

    Parameters:
    - `filePath`: Path to Video file.
    - `subPath`: Path to subtitile file.
    - `user_id`: To get parent directory.
    - `file_list`: List of all input files

    returns: Merged Video File Path
    """
    LOGGER.info("Generating mux command")
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    videoData = ffmpeg.probe(filename=filePath)
    videoStreamsData = videoData.get("streams")
    subTrack = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i]["codec_type"] == "subtitle":
            subTrack += 1
    for i in file_list:
        muxcmd.append("-i")
        muxcmd.append(i)
    muxcmd.append("-map")
    muxcmd.append("0:v:0")
    muxcmd.append("-map")
    muxcmd.append("0:a:?")
    muxcmd.append("-map")
    muxcmd.append("0:s:?")
    for j in range(1, (len(file_list))):
        muxcmd.append("-map")
        muxcmd.append(f"{j}:s")
        muxcmd.append(f"-metadata:s:s:{subTrack}")
        muxcmd.append(f"title=Track {subTrack + 1} - tg@yashoswalyo")
        subTrack += 1
    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("srt")
    muxcmd.extend(metadata_args)
    muxcmd.append(
        f"./downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv")
    LOGGER.info("Sub muxing")
    process = await asyncio.create_subprocess_exec(
        *muxcmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    return f"downloads/{str(user_id)}/[@yashoswalyo]_softmuxed_video.mkv"


async def MergeAudio(videoPath: str, files_list: list, user_id):
    LOGGER.info("Generating Mux Command")
    metadata_args = generate_metadata_args(user_id)
    muxcmd = []
    muxcmd.append("ffmpeg")
    muxcmd.append("-hide_banner")
    videoData = ffmpeg.probe(filename=videoPath)
    videoStreamsData = videoData.get("streams")
    audioTracks = 0
    for i in files_list:
        muxcmd.append("-i")
        muxcmd.append(i)
    muxcmd.append("-map")
    muxcmd.append("0:v:0")
    muxcmd.append("-map")
    muxcmd.append("0:a:?")
    audioTracks = 0
    for i in range(len(videoStreamsData)):
        if videoStreamsData[i]["codec_type"] == "audio":
            muxcmd.append(f"disposition:a:{audioTracks}")
            muxcmd.append("0")
            audioTracks += 1
    fAudio = audioTracks
    for j in range(1, len(files_list)):
        muxcmd.append("-map")
        muxcmd.append(f"{j}:a")
        muxcmd.append(f"-metadata:s:a:{audioTracks}")
        muxcmd.append(f"title=Track {audioTracks + 1} - tg@yashoswalyo")
        audioTracks += 1
    muxcmd.append(f"-disposition:s:a:{fAudio}")
    muxcmd.append("default")
    muxcmd.append("-map")
    muxcmd.append("0:s:?")
    muxcmd.append("-c:v")
    muxcmd.append("copy")
    muxcmd.append("-c:a")
    muxcmd.append("copy")
    muxcmd.append("-c:s")
    muxcmd.append("copy")
    muxcmd.extend(metadata_args)
    muxcmd.append(f"downloads/{str(user_id)}/[@yashoswalyo]_export.mkv")

    LOGGER.info(muxcmd)
    process = await asyncio.create_subprocess_exec(
        *muxcmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    LOGGER.info(process)
    return f"downloads/{str(user_id)}/[@yashoswalyo]_export.mkv"


async def cult_small_video(
        video_file,
        output_directory,
        start_time,
        end_time,
        format_):

    out_put_file_name = (
        output_directory + str(round(time.time())) + "." + format_.lower()
    )
    file_generator_command = [
        "ffmpeg",
        "-ss",
        str(start_time),
        "-to",
        str(end_time),
        "-i",
        video_file,
        "-async",
        "1",
        "-strict",
        "-2",
        out_put_file_name,
    ]
    process = await asyncio.create_subprocess_exec(
        *file_generator_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()
    LOGGER.info(e_response)
    LOGGER.info(t_response)
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    else:
        return None


async def take_screen_shot(video_file, output_directory, ttl):
    """
    This functions generates custom_thumbnail / Screenshot.

    Parameters:

    - `video_file`: Path to video file.
    - `output_directory`: Path where to save thumbnail
    - `ttl`: Timestamp to generate ss

    returns: This will return path of screenshot
    """

    out_put_file_name = os.path.join(
        output_directory, str(
            time.time()) + ".jpg")
    if video_file.upper().endswith(
        (
            "MKV",
            "MP4",
            "WEBM",
            "AVI",
            "MOV",
            "OGG",
            "WMV",
            "M4V",
            "TS",
            "MPG",
            "MTS",
            "M2TS",
            "3GP",
        )
    ):
        file_genertor_command = [
            "ffmpeg",
            "-ss",
            str(ttl),
            "-i",
            video_file,
            "-vframes",
            "1",
            out_put_file_name,
        ]

        process = await asyncio.create_subprocess_exec(
            *file_genertor_command,

            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

    if os.path.exists(out_put_file_name):
        return out_put_file_name
    else:
        return None


async def extractVideo(path_to_file, user_id):
    """
    docs
    """
    dir_name = os.path.dirname(os.path.dirname(path_to_file))
    if not os.path.exists(path_to_file):
        return None
    if not os.path.exists(dir_name + "/extract"):
        os.makedirs(dir_name + "/extract")
    videoStreamsData = ffmpeg.probe(path_to_file)

    extract_dir = dir_name + "/extract"
    videos = []
    for stream in videoStreamsData.get("streams"):
        try:
            if stream["codec_type"] == "video":
                videos.append(stream)
        except Exception as e:
            LOGGER.warning(e)
    for video in videos:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        try:
            index = video["index"]
            extractcmd.append(f"0:{index}")
            output_file = str(video["index"]) + "." + \
                video["codec_name"] + ".mkv"
            extractcmd.append("-c")
            extractcmd.append("copy")
            extractcmd.append(f"{extract_dir}/{output_file}")
            LOGGER.info(extractcmd)
            process = await asyncio.create_subprocess_exec(
                *extractcmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except Exception as e:
            LOGGER.error(f"Something went wrong: {e}")
    if get_path_size(extract_dir) > 0:
        return extract_dir
    else:
        LOGGER.warning(f"{extract_dir} is empty")
        return None


async def extractAudios(path_to_file, user_id):
    """
    docs
    """
    dir_name = os.path.dirname(os.path.dirname(path_to_file))
    if not os.path.exists(path_to_file):
        return None
    if not os.path.exists(dir_name + "/extract"):
        os.makedirs(dir_name + "/extract")
    videoStreamsData = ffmpeg.probe(path_to_file)

    extract_dir = dir_name + "/extract"
    audios = []
    for stream in videoStreamsData.get("streams"):
        try:
            if stream["codec_type"] == "audio":
                audios.append(stream)
        except Exception as e:
            LOGGER.warning(e)
    for audio in audios:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        try:
            index = audio["index"]
            extractcmd.append(f"0:{index}")
            try:
                output_file: str = (
                    "("
                    + audio["tags"]["language"]
                    + ") "
                    + audio["tags"]["title"]
                    + "."
                    + audio["codec_type"]
                    + ".mka"
                )
                output_file = output_file.replace(" ", ".")
            except BaseException:
                output_file = str(audio["index"]) + \
                    "." + audio["codec_type"] + ".mka"
            extractcmd.append("-c")
            extractcmd.append("copy")
            extractcmd.append(f"{extract_dir}/{output_file}")
            LOGGER.info(extractcmd)
            process = await asyncio.create_subprocess_exec(
                *extractcmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except Exception as e:
            LOGGER.error(f"Something went wrong: {e}")
    if get_path_size(extract_dir) > 0:
        return extract_dir
    else:
        LOGGER.warning(f"{extract_dir} is empty")
        return None


async def HardSubVideo(video_path: str, sub_path: str, output_path: str):
    """
    Burns subtitles into the video (Hardsub).
    """
    hardsub_cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"subtitles='{sub_path}'",
        "-c:a", "copy",
        "-y", output_path
    ]
    LOGGER.info(f"Starting hardsub for {video_path} with {sub_path}")
    process = await asyncio.create_subprocess_exec(
        *hardsub_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()

    if process.returncode != 0:
        LOGGER.error(f"Hardsub failed for {video_path}")
        return False

    LOGGER.info(f"Hardsub completed: {output_path}")
    return True


async def encode_video(video_path: str, output_path: str, **kwargs):
    """
    Re-encodes a video using libx264.
    """
    crf = kwargs.get("crf", "27")
    preset = kwargs.get("preset", "veryfast")
    codec = kwargs.get("codec", "libx264")
    resolution = kwargs.get("resolution", "854x480")
    audio_b = kwargs.get("audio_b", "48k")

    metadata_args = generate_metadata_args(
        kwargs.get('user_id')) if kwargs.get('user_id') else []
    encode_cmd = [
        "ffmpeg",
        "-i", video_path,
        "-c:v", codec,
        "-preset", preset,
        "-crf", crf,
        "-s", resolution,
        "-c:a", "aac",
        "-b:a", audio_b,
        *metadata_args,
        "-y", output_path
    ]
    LOGGER.info(f"Starting encoding for {video_path}")
    process = await asyncio.create_subprocess_exec(
        *encode_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()

    if process.returncode != 0:
        LOGGER.error(f"Encoding failed for {video_path}")
        return False

    LOGGER.info(f"Encoding completed: {output_path}")
    return True


async def extractSubtitles(path_to_file, user_id):
    """
    docs
    """
    dir_name = os.path.dirname(os.path.dirname(path_to_file))
    if not os.path.exists(path_to_file):
        return None
    if not os.path.exists(dir_name + "/extract"):
        os.makedirs(dir_name + "/extract")
    videoStreamsData = ffmpeg.probe(path_to_file)

    extract_dir = dir_name + "/extract"
    subtitles = []
    for stream in videoStreamsData.get("streams"):
        try:
            if stream["codec_type"] == "subtitle":
                subtitles.append(stream)
        except Exception as e:
            LOGGER.warning(e)
    for subtitle in subtitles:
        extractcmd = []
        extractcmd.append("ffmpeg")
        extractcmd.append("-hide_banner")
        extractcmd.append("-i")
        extractcmd.append(path_to_file)
        extractcmd.append("-map")
        try:
            index = subtitle["index"]
            extractcmd.append(f"0:{index}")
            try:
                output_file: str = (
                    "("
                    + subtitle["tags"]["language"]
                    + ") "
                    + subtitle["tags"]["title"]
                    + "."
                    + subtitle["codec_type"]
                    + ".mka"
                )
                output_file = output_file.replace(" ", ".")
            except BaseException:
                try:
                    output_file = (
                        str(subtitle["index"])
                        + "."
                        + subtitle["tags"]["language"]
                        + "."
                        + subtitle["codec_type"]
                        + ".mka"
                    )
                except BaseException:
                    output_file = (
                        str(subtitle["index"]) + "." + subtitle["codec_type"] + ".mka"
                    )
            extractcmd.append("-c")
            extractcmd.append("copy")
            extractcmd.append(f"{extract_dir}/{output_file}")
            LOGGER.info(extractcmd)
            process = await asyncio.create_subprocess_exec(
                *extractcmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except Exception as e:
            LOGGER.error(f"Something went wrong: {e}")
    if get_path_size(extract_dir) > 0:
        return extract_dir
    else:
        LOGGER.warning(f"{extract_dir} is empty")
        return None
