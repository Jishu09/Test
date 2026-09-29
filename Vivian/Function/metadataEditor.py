from pyrogram import Client, filters
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message)

from main import LOGGER
from Vivian.Database.database import getMetadata, setMetadata


def get_metadata_markup(uid):
    metadata = getMetadata(uid)

    markup = [
        [InlineKeyboardButton(f"Title: {metadata.get('title', 'Not set')}", callback_data="metadata_title"),
         InlineKeyboardButton(f"Author: {metadata.get('author', 'Not set')}", callback_data="metadata_author")],
        [InlineKeyboardButton(f"Artist: {metadata.get('artist', 'Not set')}", callback_data="metadata_artist"),
         InlineKeyboardButton(f"Audio: {metadata.get('audio', 'Not set')}", callback_data="metadata_audio")],
        [InlineKeyboardButton(f"Subtitle: {metadata.get('subtitle', 'Not set')}", callback_data="metadata_subtitle"),
         InlineKeyboardButton(f"Video: {metadata.get('video', 'Not set')}", callback_data="metadata_video")],
        [InlineKeyboardButton(f"Encoded By: {metadata.get('encoded_by', 'Not set')}", callback_data="metadata_encoded_by"),
         InlineKeyboardButton(f"Custom Tag: {metadata.get('custom_tag', 'Not set')}", callback_data="metadata_custom_tag")],
        [InlineKeyboardButton(f"Comment: {metadata.get('comment', 'Not set')}", callback_data="metadata_comment"),
         InlineKeyboardButton(f"Dubbed By: {metadata.get('dubbed_by', 'Not set')}", callback_data="metadata_dubbed_by")],
        [InlineKeyboardButton(f"Channel: {metadata.get('channel', 'Not set')}", callback_data="metadata_channel"),
         InlineKeyboardButton(f"Website: {metadata.get('website', 'Not set')}", callback_data="metadata_website")],
        [InlineKeyboardButton(f"Copyright: {metadata.get('copyright', 'Not set')}", callback_data="metadata_copyright"),
         InlineKeyboardButton(f"Publisher: {metadata.get('publisher', 'Not set')}", callback_data="metadata_publisher")],
        [InlineKeyboardButton(f"Encoder: {metadata.get('encoder', 'Not set')}", callback_data="metadata_encoder"),
         InlineKeyboardButton(f"Source: {metadata.get('source', 'Not set')}", callback_data="metadata_source")],
        [InlineKeyboardButton(f"Studio: {metadata.get('studio', 'Not set')}", callback_data="metadata_studio"),
         InlineKeyboardButton(f"Official Site: {metadata.get('official_site', 'Not set')}", callback_data="metadata_official_site")],
        [InlineKeyboardButton("Close", callback_data="close")]
    ]
    return InlineKeyboardMarkup(markup)


def get_metadata_text(uid):
    metadata = getMetadata(uid)
    text = "㊂ Metadata Configurator :\n\n"
    text += f"➲ Title: {metadata.get('title', 'Not set')}\n"
    text += f"➲ Author: {metadata.get('author', 'Not set')}\n"
    text += f"➲ Artist: {metadata.get('artist', 'Not set')}\n"
    text += f"➲ Audio: {metadata.get('audio', 'Not set')}\n"
    text += f"➲ Subtitle: {metadata.get('subtitle', 'Not set')}\n"
    text += f"➲ Video: {metadata.get('video', 'Not set')}\n"
    text += f"➲ Encoded By: {metadata.get('encoded_by', 'Not set')}\n"
    text += f"➲ Custom Tag: {metadata.get('custom_tag', 'Not set')}\n"
    text += f"➲ Comment: {metadata.get('comment', 'Not set')}\n"
    text += f"➲ Dubbed By: {metadata.get('dubbed_by', 'Not set')}\n"
    text += f"➲ Channel: {metadata.get('channel', 'Not set')}\n"
    text += f"➲ Website: {metadata.get('website', 'Not set')}\n"
    text += f"➲ Copyright: {metadata.get('copyright', 'Not set')}\n"
    text += f"➲ Publisher: {metadata.get('publisher', 'Not set')}\n"
    text += f"➲ Encoder: {metadata.get('encoder', 'Not set')}\n"
    text += f"➲ Source: {metadata.get('source', 'Not set')}\n"
    text += f"➲ Studio: {metadata.get('studio', 'Not set')}\n"
    text += f"➲ Official Site: {metadata.get('official_site', 'Not set')}\n\n"
    text += "Click on any field below to modify its value manually:"
    return text


@Client.on_message(filters.command(["metadata"]))
async def metaEditor(c: Client, m: Message):
    uid = m.from_user.id
    markup = get_metadata_markup(uid)
    text = get_metadata_text(uid)
    await m.reply_text(
        text,
        reply_markup=markup,
        quote=True,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^metadata_(.*)"))
async def handle_metadata_cb(c: Client, cb: CallbackQuery):
    field = cb.matches[0].group(1)
    uid = cb.from_user.id
    msg = await cb.message.edit_text(f"Send the new value for **{field}** (Send /cancel to cancel):")

    try:
        response = await c.listen(chat_id=cb.message.chat.id, user_id=uid, timeout=60)

        if not response.text or response.text == "/cancel":
            await msg.delete()
            await response.delete()
            markup = get_metadata_markup(uid)
            text = get_metadata_text(uid)
            await cb.message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)
            return

        new_val = response.text
        metadata = getMetadata(uid)
        metadata[field] = new_val
        setMetadata(uid, metadata)

        await msg.delete()
        await response.delete()

        markup = get_metadata_markup(uid)
        text = get_metadata_text(uid)
        await cb.message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)

    except Exception as e:
        LOGGER.error(f"Error in metadata configurator: {e}")
        await cb.message.reply_text("An error occurred or you took too long.")
