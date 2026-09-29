
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from main import UPLOAD_AS_DOC, UPLOAD_DESTINATION
from Vivian.Function.utils import UserSettings


@Client.on_message(filters.command(["start"]))
async def start_handler(c: Client, m: Message):
    user = UserSettings(m.from_user.id, m.from_user.first_name)

    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(
            text=f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can\'t use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ",
            quote=True,
        )
        return
    await m.reply_photo(
        photo="https://graph.org/file/5f70f4eb9b9c86352abc0-e511ba08e99bac479c.jpg",
        caption=f"<b><blockquote>𝖧𝖾𝗒 {m.from_user.first_name}!</blockquote>\n\n𝖳𝗁𝗂𝗌 𝗂𝗌 𝖺 𝖳𝖾𝗅𝖾𝗀𝗋𝖺𝗆 𝖵𝗂𝖽𝖾𝗈 𝖳𝗈𝗈𝗅 𝖡𝗈𝗍.\n\n𝖨 𝖼𝖺𝗇 𝖽𝗈 𝖬𝖺𝗋𝗀𝖾, 𝖤𝗇𝖼𝗈𝖽𝖾, 𝖠𝗋𝖼𝗁𝗂𝗏𝖾, 𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 𝖲𝖼𝗋𝖾𝖾𝗇𝗌𝗁𝗈𝗍𝗌 𝖾𝗍𝖼.\n\n𝖢𝗁𝖾𝖼𝗄 𝗆𝗒 𝖺𝗅𝗅 𝖿𝖾𝖺𝗍𝗎𝗋𝖾𝗌 𝖻𝗒 /help 𝖼𝗈𝗆𝗆𝖺𝗇𝖽𝗌\n\n<blockquote>➤ 𝖯𝗈𝗐𝖾𝗋𝖾𝚍 𝖻𝗒 @Tongxin_Tech</blockquote></b>",
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Help 💡", callback_data="help"),
                    InlineKeyboardButton("About ℹ️", callback_data="about"),
                ],
                [
                    InlineKeyboardButton("Updates 📢", url="https://t.me/Tongxin_Tech"),
                    InlineKeyboardButton("Support 👨‍💻", url="https://t.me/Tongxin_Admin"),
                ]
            ]
        ),
    )
    del user


@Client.on_message(filters.command(["setmedia"]))
async def setmedia_handler(c: Client, m: Message):
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(
            text=f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can't use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ",
            quote=True,
        )
        return

    current = "Document" if UPLOAD_AS_DOC.get(
        f"{m.from_user.id}", False) else "Video"
    await m.reply_text(
        text=f"Current upload format: **{current}**\n\nChoose the format to upload media:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🎞️ Video", callback_data="cmd_setmedia_video"),
                    InlineKeyboardButton("📁 Document", callback_data="cmd_setmedia_document"),
                ],
                [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
            ]
        ),
        quote=True,
    )


@Client.on_message(filters.command(["setupload"]))
async def setupload_handler(c: Client, m: Message):
    if m.from_user.id != int(Config.OWNER):
        await m.reply_text(
            text=f"Hi **{m.from_user.first_name}**\n\n 🛡️ Unfortunately you can't use me\n\n**Contact: 🈲 @{Config.OWNER_USERNAME}** ",
            quote=True,
        )
        return

    current = UPLOAD_DESTINATION.get(f"{m.from_user.id}", "telegram")
    await m.reply_text(
        text=f"Current upload destination: **{current.capitalize()}**\n\nChoose the upload destination:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📤 Telegram", callback_data="cmd_setupload_telegram"),
                    InlineKeyboardButton("📤 GoFile", callback_data="cmd_setupload_gofile"),
                ],
                [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
            ]
        ),
        quote=True,
    )


@Client.on_message(filters.command(["help"]))
async def help_msg(c: Client, m: Message):
    await m.reply_text(
        text="""**Follow These Steps:

1) Send me the custom thumbnail (optional).
2) Send two or more Your Videos Which you want to merge
3) After sending all files select merge options
4) Select rename if you want to give custom file name else press default**""",
        quote=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Close 🔐", callback_data="close")]]
        ),
    )
