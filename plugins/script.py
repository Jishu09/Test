START_TEXT = """<b>Hᴇʟʟᴏ {first}!</b>

<b>ɪ ᴀᴍ ᴀᴜᴛᴏ ᴄᴀᴘᴛɪᴏɴ ʙᴏᴛ ᴡɪᴛʜ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.

Fᴏʀ ᴍᴏʀᴇ ɪɴғᴏ ʜᴏᴡ ᴛᴏ ᴜsᴇ ᴍᴇ ᴄʟɪᴄᴋ ᴏɴ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ɢɪᴠᴇɴ ʙᴇʟᴏᴡ.</b>

<b>Mᴀɪɴᴛᴀɪɴᴇᴅ ʙʏ » <a href='https://t.me/Rare_Bots_Hub'>ʀᴀʀᴇ ʙᴏᴛ ʜᴜʙ</a></b>"""

HELP_TEXT = """📖 ᴄᴏᴍᴍᴀɴᴅ ɢᴜɪᴅᴇ

ᴍᴀɴᴀɢᴇ ᴄʜᴀɴɴᴇʟs (ᴘᴍ ᴏɴʟʏ):
/channels — Open settings dashboard

ᴄʜᴀɴɴᴇʟ sᴇᴛᴜᴘ (ᴜsᴇ ɪɴ ᴄʜᴀɴɴᴇʟ):
/connect /disconnect
/setcaption `<template>` /mycaption /resetcaption
/autocaption `on/off`
/filter `<video,document,audio>`
/setregex `<field> <pattern>`
/addbutton `[Text][buttonurl:url]` /delbutton
/removeword `<word>` /replaceword `<old> <new>`
/clearwords
/setprefix `<text>` /delprefix
/setsuffix `<text>` /delsuffix
/captionreversal `on/off` /mediadetails `on/off`
/captionfont `<normal|bold|italic|mono|underline>`"""

OWNER_HELP_TEXT = """👑 **ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs**

ғᴏʀᴄᴇ-sᴜʙsᴄʀɪʙᴇ:
/addfsub `<chat_id> <mode>` — Add Fsub
/delfsub `<chat_id>` — Remove Fsub
/listfsub — List all Fsub channels

ʙʀᴏᴀᴅᴄᴀsᴛ:
/broadcast — DM all users
/cbroadcast — Post to all channels

ᴀᴅᴍɪɴ ᴄᴏɴᴛʀᴏʟs:
/stats — View statistics
/ban `<user_id>` 
/unban `<user_id>`
/maintenance `on/off`
/restart — Restart bot
/addsudo `<user_id>`
/delsudo `<user_id>`
"""

ABOUT_TEXT = """<b>›› ᴄᴏᴍᴍᴜɴɪᴛʏ: <a href='https://t.me/Rare_Bots_Hub'>ʀᴀʀᴇ ʙᴏᴛ ʜᴜʙ</a>
<blockquote expandable>›› ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ: <a href='https://t.me/Rare_Bots_Support'>ʙᴏᴛ ꜱᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ</a>
›› ʟᴀɴɢᴜᴀɢᴇ: <a href='https://docs.python.org/3/'>Pʏᴛʜᴏɴ 3</a>
›› ʟɪʙʀᴀʀʏ: <a href='https://docs.pyrogram.org/'>Pʏʀᴏɢʀᴀᴍ ᴠ2</a>
›› ᴅᴀᴛᴀʙᴀsᴇ: <a href='https://www.mongodb.com/docs/'>Mᴏɴɢᴏ ᴅʙ</a>
›› ᴅᴇᴠᴇʟᴏᴘᴇʀ: <a href='https://t.me/UR_Sourov'>ꜱᴏᴜʀᴏᴠ</a></b></blockquote></b>"""

CAPTION_GUIDE = """🧩 You can set your own caption template using the placeholders below.
The bot will automatically replace them with real file data when sending a file.

Available Fillings:

🎥 Video Fillings:
• {filename} = ғɪʟᴇ ɴᴀᴍᴇ.
• {filesize} = ᴏʀɪɢɪɴᴀʟ ғɪʟᴇ sɪᴢᴇ.
• {duration} = ᴅᴜʀᴀᴛɪᴏɴ ғʀᴏᴍ ᴠɪᴅᴇᴏ.
• {height} = ʜᴇɪɢʜᴛ ᴏғ ᴠɪᴅᴇᴏ.
• {width} = ᴡɪᴅᴛʜ ᴏғ ᴠɪᴅᴇᴏ.
• {resolution} = ʀᴇsᴏʟᴜᴛɪᴏɴ ᴏғ ᴠɪᴅᴇᴏ.
• {ext} = ᴇxᴛ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ. [ᴍᴘ𝟺, ᴍᴘ𝟹, ᴍᴋᴠ, ᴇᴛᴄ...]
• {mime_type} = ᴍɪᴍᴇ ᴛʏᴘᴇ ᴏғ ᴠɪᴅᴇᴏ.

🎵 Audio Fillings:
• {title} = ᴀᴜᴅɪᴏ ᴛɪᴛʟᴇ ɴᴀᴍᴇ.
• {artist} = ᴀᴜᴅɪᴏ ᴀʀᴛɪꜱᴛ ɴᴀᴍᴇ.
• {duration} = ᴅᴜʀᴀᴛɪᴏɴ ᴏғ ᴀᴜᴅɪᴏ.
• {filename} = ғɪʟᴇ ɴᴀᴍᴇ.
• {filesize} = ᴏʀɪɢɪɴᴀʟ ғɪʟᴇ sɪᴢᴇ.
• {ext} = ᴇxᴛ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ. [ᴍᴘ𝟹, ᴍ𝟺ᴀ, ᴇᴛᴄ...]
• {mime_type} = ᴍɪᴍᴇ ᴛʏᴘᴇ ᴏғ ᴀᴜᴅɪᴏ.

🖼️ Photo Fillings:
• {caption} = ғɪʟᴇ ᴄᴀᴘᴛɪᴏɴ.(ᴡɪᴛʜᴏᴜᴛ ʜᴛᴍʟ)
• {html_caption} = ғɪʟᴇ ᴄᴀᴘᴛɪᴏɴ.(ᴡɪᴛʜ ʜᴛᴍʟ)
• {filesize} = ᴘʜᴏᴛᴏ ꜱɪᴢᴇ.
• {width} = ᴘʜᴏᴛᴏ ᴡɪᴅᴛʜ.
• {height} = ᴘʜᴏᴛᴏ ʜᴇɪɢʜᴛ.
• {mime_type} = ᴘʜᴏᴛᴏ ᴍɪᴍᴇ ᴛʏᴘᴇ (ɪғ ᴀᴠᴀɪʟᴀʙʟᴇ).
• {wish} = ᴡɪꜱʜ [ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ, ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ, ᴇᴛᴄ...]

📄 Document Fillings:
• {filename} = ғɪʟᴇ ɴᴀᴍᴇ.
• {filesize} = ᴏʀɪɢɪɴᴀʟ ғɪʟᴇ sɪᴢᴇ.
• {ext} = ᴇxᴛ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ. [ᴘᴅғ, ᴅᴏᴄx, ᴇᴛᴄ...]

📝 Other Fillings (Common):
• {caption} = ғɪʟᴇ ᴄᴀᴘᴛɪᴏɴ.(ᴡɪᴛʜᴏᴜᴛ ʜᴛᴍʟ)
• {html_caption} = ғɪʟᴇ ᴄᴀᴘᴛɪᴏɴ.(ᴡɪᴛʜ ʜᴛᴍʟ)
• {language} = ʟᴀɴɢᴜᴀɢᴇs ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ.
• {year} = ʏᴇᴀʀ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ.
• {quality} = ǫᴜᴀʟɪᴛʏ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ.
• {season} = ꜱᴇᴀꜱᴏɴ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ.
• {episode} = ᴇᴘɪꜱᴏᴅᴇ ғʀᴏᴍ ғɪʟᴇ ɴᴀᴍᴇ.
• {wish} = ᴡɪꜱʜ [ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ, ɢᴏᴏᴅ ᴀғᴛᴇʀɴᴏᴏɴ, ᴇᴛᴄ...]

📝 NOTE: ᴅᴏɴ'ᴛ ᴜsᴇ ᴀɴʏ ᴜɴᴋɴᴏᴡɴ ᴠᴀʀɪᴀʙʟᴇs."""

BUTTON_GUIDE = """🔘 Custom Button

You can set an inline button on every auto-captioned post.

Format:
[Button Text][buttonurl:https://example.com]

Multiple buttons on the same row — separate with &&:
[Button 1][buttonurl:https://a.com] && [Button 2][buttonurl:https://b.com]

Put each row on its own line."""

WORDS_GUIDE = """🔤 Text Settings Guide

With these options, you can clean up the original file caption before your template is applied.

• 🧹 Remove Text — delete any word or phrase.
   ➤ Example: remove the word "Telegram".

• ♻️ Replace Text — change specific words or phrases.
   ➤ Example: replace "Telegram" with "WhatsApp"."""
