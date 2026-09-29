import asyncio
import html
import json
import os
import re

import aiofiles
import aiohttp
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from main import LOGGER as log

try:
    from telegraph import Telegraph
except ImportError:
    Telegraph = None


MEDIAINFO_DIR = "Mediainfo"

SECTION_DICT = {
    'General': '🗒',
    'Video': '🎞',
    'Audio': '🔊',
    'Text': '🔠',
    'Menu': '🗃'
}


def _parse_ffprobe_to_mediainfo(raw: str) -> str:
    """Convert ffprobe JSON output into clean Mediainfo-like sections."""
    try:
        data = json.loads(raw)
    except Exception as e:
        return f"<pre>Error parsing metadata: {str(e)}</pre>"

    html_out = ""

    def format_kv(k, v):
        if v is None or str(v).strip() == "":
            return ""
        return f"{html.escape(str(k)).ljust(40)} : {html.escape(str(v))}\n"

    fmt = data.get("format", {})
    if fmt:
        html_out += "<h4>🗒 General</h4>\n<pre>\n"

        file_name = fmt.get("filename", "")
        if "/" in file_name:
            file_name = file_name.split("/")[-1]
        if file_name:
            html_out += format_kv("Complete name", file_name)

        if "format_long_name" in fmt:
            html_out += format_kv("Format", fmt["format_long_name"])
        elif "format_name" in fmt:
            html_out += format_kv("Format", fmt["format_name"])

        if "size" in fmt:
            try:
                html_out += format_kv("File size",
                                      f"{float(fmt['size']) / (1024 * 1024):.2f} MiB")
            except BaseException:
                pass

        if "duration" in fmt:
            try:
                secs = float(fmt["duration"])
                mins = int(secs // 60)
                rem = int(secs % 60)
                html_out += format_kv("Duration", f"{mins} min {rem} s")
            except BaseException:
                pass

        if "bit_rate" in fmt:
            try:
                html_out += format_kv("Overall bit rate",
                                      f"{int(fmt['bit_rate']) // 1000} kb/s")
            except BaseException:
                pass

        for k, v in fmt.get("tags", {}).items():
            html_out += format_kv(k.replace("_", " ").title(), v)

        html_out += "</pre><br>\n"

    v_idx, a_idx, s_idx = 1, 1, 1
    for stream in data.get("streams", []):
        ctype = stream.get("codec_type", "unknown")
        if ctype == "video":
            html_out += f"<h4>🎞 Video #{v_idx}</h4>\n<pre>\n"
            v_idx += 1
        elif ctype == "audio":
            html_out += f"<h4>🔊 Audio #{a_idx}</h4>\n<pre>\n"
            a_idx += 1
        elif ctype == "subtitle":
            html_out += f"<h4>🔠 Subtitle #{s_idx}</h4>\n<pre>\n"
            s_idx += 1
        else:
            html_out += "<h4>🔠 Stream</h4>\n<pre>\n"

        html_out += format_kv("ID", stream.get("index", ""))
        html_out += format_kv("Format", stream.get("codec_name", "").upper())
        if "codec_long_name" in stream:
            html_out += format_kv("Format/Info", stream["codec_long_name"])
        if "profile" in stream:
            html_out += format_kv("Format profile", stream["profile"])
        html_out += format_kv("Codec ID",
                              stream.get("codec_tag_string",
                                         stream.get("codec_tag",
                                                    "")))

        if "duration" in stream:
            try:
                secs = float(stream["duration"])
                mins = int(secs // 60)
                rem = int(secs % 60)
                html_out += format_kv("Duration", f"{mins} min {rem} s")
            except BaseException:
                pass

        if "bit_rate" in stream:
            try:
                html_out += format_kv("Bit rate",
                                      f"{int(stream['bit_rate']) // 1000} kb/s")
            except BaseException:
                pass

        if ctype == "video":
            if "width" in stream:
                html_out += format_kv("Width", f"{stream['width']} pixels")
            if "height" in stream:
                html_out += format_kv("Height", f"{stream['height']} pixels")
            if "display_aspect_ratio" in stream:
                html_out += format_kv("Display aspect ratio",
                                      stream['display_aspect_ratio'])

            if "r_frame_rate" in stream and stream["r_frame_rate"] != "0/0":
                try:
                    num, den = map(float, stream["r_frame_rate"].split("/"))
                    if den > 0:
                        html_out += format_kv("Frame rate",
                                              f"{num / den:.3f} FPS")
                except BaseException:
                    pass

            if "pix_fmt" in stream:
                html_out += format_kv("Color space", stream["pix_fmt"].upper())
            if "color_range" in stream:
                html_out += format_kv("Color range",
                                      stream["color_range"].title())

        elif ctype == "audio":
            if "channels" in stream:
                c = stream["channels"]
                html_out += format_kv("Channel(s)",
                                      f"{c} channel{'s' if c > 1 else ''}")
            if "channel_layout" in stream:
                html_out += format_kv("Channel layout",
                                      stream["channel_layout"])
            if "sample_rate" in stream:
                try:
                    html_out += format_kv("Sampling rate",
                                          f"{float(stream['sample_rate']) / 1000:.1f} kHz")
                except BaseException:
                    pass

        disp = stream.get("disposition", {})
        if "default" in disp:
            html_out += format_kv("Default",
                                  "Yes" if disp["default"] == 1 else "No")
        if "forced" in disp:
            html_out += format_kv("Forced",
                                  "Yes" if disp["forced"] == 1 else "No")

        for k, v in stream.get("tags", {}).items():
            html_out += format_kv(k.replace("_", " ").title(), v)

        html_out += "</pre><br>\n"

    chapters = data.get("chapters", [])
    if chapters:
        html_out += "<h4>🗃 Menu</h4>\n<pre>\n"
        for chap in chapters:
            start = chap.get("start_time", 0)
            try:
                secs = float(start)
                h = int(secs // 3600)
                m = int((secs % 3600) // 60)
                s = int(secs % 60)
                ms = int((secs - int(secs)) * 1000)
                start_str = f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
            except BaseException:
                start_str = str(start)

            title = chap.get("tags", {}).get("title", "")
            if start_str or title:
                html_out += f"{
                    html.escape(start_str).ljust(35)} : {
                    html.escape(title)}\n"
        html_out += "</pre><br>\n"

    return html_out


async def _run_cmd(cmd: list) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out = (stdout or b"").decode("utf-8", errors="ignore").strip()
        return out
    except Exception:
        return ""


async def _get_info_text(file_path: str) -> tuple[str, str]:
    """Tries mediainfo first; falls back to ffprobe if mediainfo is missing."""

    out = await _run_cmd(["mediainfo", file_path])
    if out and "not found" not in out.lower() and "no such file" not in out.lower():
        return out, "mediainfo"

    out = await _run_cmd([
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        file_path,
    ])
    if out:
        return out, "ffprobe"

    return "", ""


async def _download_telegram_media(
        client: Client,
        message: Message,
        media,
        dest: str) -> None:
    size = getattr(media, "file_size", 0) or 0
    if size and size <= 50000000:
        await message.download(file_name=dest)
    else:
        try:

            async for chunk in client.stream_media(media, limit=25):
                async with aiofiles.open(dest, "ab") as f:
                    await f.write(chunk)
        except Exception:
            await message.download(file_name=dest)


_telegraph = None
if Telegraph is not None:
    try:
        _telegraph = Telegraph(domain='graph.org')
        _telegraph.create_account(short_name="MediaInfoX")
    except Exception:
        _telegraph = None


async def _publish_telegraph(
        title: str,
        content_html: str,
        author_name: str,
        author_url: str) -> str:
    if _telegraph is None:
        raise RuntimeError(
            "telegraph package not installed or account creation failed")
    page = await asyncio.to_thread(
        _telegraph.create_page,
        title=title, html_content=content_html,
        author_name=author_name, author_url=author_url,
    )
    return f"https://graph.org/{page['path']}"


async def gen_mediainfo(
        client: Client,
        message: Message,
        media,
        media_msg: Message):
    temp_send = await message.reply_text("<i>Generating MediaInfo...</i>", parse_mode=ParseMode.HTML)
    des_path = None

    try:
        if not os.path.isdir(MEDIAINFO_DIR):
            os.makedirs(MEDIAINFO_DIR, exist_ok=True)

        fname = getattr(
            media,
            "file_name",
            None) or f"tg_media_{
            media.file_unique_id}"
        fname = re.sub(r"[^\w.\-]+", "_", fname)[:80]
        des_path = os.path.join(MEDIAINFO_DIR, fname)

        await _download_telegram_media(client, media_msg, media, des_path)

        if not os.path.exists(des_path):
            return await temp_send.edit_text("❌ Failed to download or process the media.")

        raw, parser_type = await _get_info_text(des_path)
        if not raw:
            return await temp_send.edit_text(
                "❌ Could not read media info via ffprobe.",
                parse_mode=ParseMode.HTML,
            )

        basename = os.path.basename(des_path)
        tc = f"<h4>📌 {html.escape(basename)}</h4><br><br>\n"

        if parser_type == "mediainfo":
            tc += _parse_mediainfo_text(raw)
        else:

            tc += _parse_ffprobe_to_mediainfo(raw)

        try:
            me = await client.get_me()
            author_name = me.first_name if me.first_name else "MediaInfo X"
            author_url = f"https://t.me/{me.username}" if me.username else ""

            url = await _publish_telegraph("MediaInfo X", tc, author_name, author_url)
            await temp_send.edit_text(
                f"<b>MediaInfo:</b>\n\n➲ <b>Link:</b> {url}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        except Exception:
            txt_path = des_path + ".txt"
            async with aiofiles.open(txt_path, "w", encoding="utf-8") as f:
                await f.write(raw)
            await temp_send.delete()
            await message.reply_document(
                txt_path,
                caption=f"<b>MediaInfo:</b>\n<code>{html.escape(basename)}</code>",
                parse_mode=ParseMode.HTML,
            )
            try:
                os.remove(txt_path)
            except OSError:
                pass

    except Exception as e:
        log.error(f"mediainfo error: {e}")
        try:
            await temp_send.edit_text(f"MediaInfo Stopped due to: <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
        except Exception:
            pass
    finally:
        if des_path and os.path.exists(des_path):
            try:
                os.remove(des_path)
            except OSError:
                pass


def _parse_mediainfo_text(out: str) -> str:
    tc = ''
    trigger = False
    for line in out.split('\n'):
        for section, emoji in SECTION_DICT.items():
            if line.startswith(section):
                trigger = True
                if not line.startswith('General'):
                    tc += '</pre><br>\n'
                tc += f"<h4>{emoji} {
                    html.escape(
                        line.replace(
                            'Text',
                            'Subtitle'))}</h4>\n"
                break
        if trigger:
            tc += '<br><pre>\n'
            trigger = False
        else:
            tc += html.escape(line) + '\n'
    tc += '</pre><br>\n'
    return tc


async def _download_from_link(link: str, dest: str) -> bool:
    """Downloads just enough of a direct URL to read its media info (inspired
    by Project-Final's mediainfo.py) - most metadata lives in the header/
    early bytes for common formats, but we cap it generously since some
    containers keep the moov atom / index near the end."""
    headers = {
        "user-agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Mobile Safari/537.36"
    }
    max_bytes = 100 * 1024 * 1024
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(link, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                resp.raise_for_status()
                written = 0
                async with aiofiles.open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                        written += len(chunk)
                        if written >= max_bytes:
                            break
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception:
        return False


async def gen_mediainfo_from_link(client: Client, message: Message, link: str):
    temp_send = await message.reply_text("<i>Downloading & Generating MediaInfo...</i>", parse_mode=ParseMode.HTML)
    des_path = None

    try:
        if not os.path.isdir(MEDIAINFO_DIR):
            os.makedirs(MEDIAINFO_DIR, exist_ok=True)

        match = re.search(r"[^/]+$", link.split("?")[0])
        fname = re.sub(
            r"[^\w.\-]+",
            "_",
            match.group(0) if match else "downloaded_file")[
            :80] or "downloaded_file"
        des_path = os.path.join(MEDIAINFO_DIR, fname)

        if not await _download_from_link(link, des_path):
            return await temp_send.edit_text("❌ Couldn't download that link.")

        raw, parser_type = await _get_info_text(des_path)
        if not raw:
            return await temp_send.edit_text("❌ Could not read media info from that file.")

        basename = os.path.basename(des_path)
        tc = f"<h4>📌 {html.escape(basename)}</h4><br><br>\n"
        tc += _parse_mediainfo_text(
            raw) if parser_type == "mediainfo" else _parse_ffprobe_to_mediainfo(raw)

        try:
            me = await client.get_me()
            author_name = me.first_name if me.first_name else "MediaInfo X"
            author_url = f"https://t.me/{me.username}" if me.username else ""
            url = await _publish_telegraph("MediaInfo X", tc, author_name, author_url)
            await temp_send.edit_text(
                f"<b>MediaInfo:</b>\n\n➲ <b>Link:</b> {url}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        except Exception:
            txt_path = des_path + ".txt"
            async with aiofiles.open(txt_path, "w", encoding="utf-8") as f:
                await f.write(raw)
            await temp_send.delete()
            await message.reply_document(
                txt_path,
                caption=f"<b>MediaInfo:</b>\n<code>{html.escape(basename)}</code>",
                parse_mode=ParseMode.HTML,
            )
            try:
                os.remove(txt_path)
            except OSError:
                pass

    except Exception as e:
        log.error(f"mediainfo (link) error: {e}")
        try:
            await temp_send.edit_text(f"MediaInfo Stopped due to: <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
        except Exception:
            pass
    finally:
        if des_path and os.path.exists(des_path):
            try:
                os.remove(des_path)
            except OSError:
                pass


@Client.on_message(filters.command("mediainfo"))
async def mediainfo_cmd(client: Client, message: Message):
    rply = message.reply_to_message
    help_msg = (
        "<b>𝖬𝖾𝖽𝗂𝖺𝖨𝗇𝖿𝗈 𝖷</b>\n\n"
        "<b>𝖡𝗒 𝗋𝖾𝗉𝗅𝗒𝗂𝗇𝗀 𝗍𝗈 𝗆𝖾𝖽𝗂𝖺:</b>\n"
        "<code>/mediainfo</code>\n\n"
        "<b>𝖡𝗒 𝗋𝖾𝗉𝗅𝗒𝗂𝗇𝗀 𝗍𝗈/𝗌𝖾𝗇𝖽𝗂𝗇𝗀 𝖺 𝖽𝗈𝗐𝗇𝗅𝗈𝖺𝖽 𝗅𝗂𝗇𝗄:</b>\n"
        "<code>/mediainfo &lt;link&gt;</code>"
    )

    link = None
    if len(message.command) > 1:
        link = message.command[1]
    elif rply and rply.text and re.match(r"^https?://", rply.text.strip()):
        link = rply.text.strip()

    if link:
        return await gen_mediainfo_from_link(client, message, link)

    if rply:
        media = next(
            (
                x
                for x in (
                    rply.document,
                    rply.video,
                    rply.audio,
                    rply.voice,
                    rply.animation,
                    rply.video_note,
                )
                if x is not None
            ),
            None,
        )
        if media:
            return await gen_mediainfo(client, message, media=media, media_msg=rply)
        return await message.reply_text(help_msg, parse_mode=ParseMode.HTML)

    return await message.reply_text(help_msg, parse_mode=ParseMode.HTML)


__module__ = "𝖬𝖾𝖽𝗂𝖺𝖨𝗇𝖿𝗈"

__help__ = """**𝖬𝖾𝖽𝗂𝖺𝖨𝗇𝖿𝗈 𝖷**

✧ `/mediainfo` (𝗋𝖾𝗉𝗅𝗒 𝗍𝗈 𝗏𝗂𝖽𝖾𝗈/𝖺𝗎𝖽𝗂𝗈/𝖽𝗈𝖼𝗎𝗆𝖾𝗇𝗍) – 𝗌𝗁𝗈𝗐 𝗍𝖾𝖼𝗁𝗇𝗂𝖼𝖺𝗅 𝗆𝖾𝖽𝗂𝖺 𝗂𝗇𝖿𝗈
✧ `/mediainfo <link>` (𝗈𝗋 𝗋𝖾𝗉𝗅𝗒 𝗍𝗈 𝖺 𝗅𝗂𝗇𝗄) – 𝗌𝖺𝗆𝖾, 𝖻𝗎𝗍 𝖿𝗈𝗋 𝖺 𝖽𝗂𝗋𝖾𝖼𝗍 𝖽𝗈𝗐𝗇𝗅𝗈𝖺𝖽 𝗅𝗂𝗇𝗄

𝖮𝗎𝗍𝗉𝗎𝗍 𝗂𝗌 𝗉𝗈𝗌𝗍𝖾𝖽 𝗈𝗇 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗉𝗁 (𝗀𝗋𝖺𝗉𝗁.𝗈𝗋𝗀) 𝗈𝗋 𝗌𝖾𝗇𝗍 𝖺𝗌 𝖺 𝖿𝗂𝗅𝖾.
"""
