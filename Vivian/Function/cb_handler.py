import asyncio

from pyrogram import Client, filters
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, Message)

from bot import delete_all, showQueue
from main import (LOGGER, UPLOAD_AS_DOC, UPLOAD_DESTINATION, formatDB, gDict,
                  queueDB)
from Vivian.Function.extractor import streamsExtractor
from Vivian.Function.utils import UserSettings
from Vivian.Tools.hardsub import hardsub_and_upload
from Vivian.Tools.marge import mergeAudio, mergeNow, mergeSub
from Vivian.Tools.pdf.pdf_utils import create_pdf_from_images
from Vivian.Tools.zip import zip_and_upload


@Client.on_callback_query()
async def callback_handler(c: Client, cb: CallbackQuery):

    if cb.data == "create_pdf":
        await cb.message.edit(
            text="Do you want to rename pdf? Default file name is **[@yashoswalyo]_merged.pdf**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👆 Default", callback_data="rename_pdf_NO"),
                        InlineKeyboardButton("✍️ Rename", callback_data="rename_pdf_YES"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data.startswith("rename_pdf_"):
        if cb.data == "rename_pdf_YES":
            await cb.message.edit("Send the new file name (with .pdf extension) within 60 seconds.")
            try:
                name_msg = await c.listen(chat_id=cb.message.chat.id, user_id=cb.from_user.id, timeout=60)
                if name_msg.text:
                    if not name_msg.text.endswith(".pdf"):
                        name_msg.text += ".pdf"
                    pdf_name = name_msg.text
                else:
                    pdf_name = "[@yashoswalyo]_merged.pdf"
            except asyncio.TimeoutError:
                await cb.message.edit("Timeout. Using default name.")
                pdf_name = "[@yashoswalyo]_merged.pdf"
        else:
            pdf_name = "[@yashoswalyo]_merged.pdf"
        await create_pdf_from_images(c, cb, pdf_name=pdf_name)
        return

    elif cb.data == "merge":
        await cb.message.edit(
            text="Do you want to rename? Default file name is **[@yashoswalyo]_merged.mkv**",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👆 Default", callback_data="rename_NO"),
                        InlineKeyboardButton("✍️ Rename", callback_data="rename_YES"),
                    ],
                    [InlineKeyboardButton("⛔ Cancel ⛔", callback_data="cancel")],
                ]
            ),
        )
        return

    elif cb.data == "cmd_setmedia_video":
        UPLOAD_AS_DOC.update({f"{cb.from_user.id}": False})
        await cb.message.edit(text="Upload format set to: **Video**")
        return

    elif cb.data == "cmd_setmedia_document":
        UPLOAD_AS_DOC.update({f"{cb.from_user.id}": True})
        await cb.message.edit(text="Upload format set to: **Document**")
        return

    elif cb.data == "cmd_setupload_telegram":
        UPLOAD_DESTINATION.update({f"{cb.from_user.id}": "telegram"})
        await cb.message.edit(text="Upload destination set to: **Telegram**")
        return

    elif cb.data == "cmd_setupload_gofile":
        UPLOAD_DESTINATION.update({f"{cb.from_user.id}": "gofile"})
        await cb.message.edit(text="Upload destination set to: **GoFile**")
        return

    elif cb.data.startswith("rename_hardsub_"):
        if "YES" in cb.data:
            await cb.message.edit("Send me a new file name for hardsub, you have 1 minute")
            try:
                new_name: Message = await c.listen(
                    chat_id=cb.message.chat.id, user_id=cb.from_user.id, timeout=60
                )
                if new_name.text:
                    new_file_name = (
                        f"downloads/{str(cb.from_user.id)}/" + new_name.text
                    )
                    await new_name.delete(True)
                else:
                    await new_name.reply_text(
                        "Invalid file name. Using default name."
                    )
                    new_file_name = (
                        f"downloads/{str(cb.from_user.id)}/[@yashoswalyo]_merged.mkv"
                    )
            except asyncio.TimeoutError:
                await cb.message.edit("Time out")
                await cb.message.delete()
                await delete_all(root=f"downloads/{cb.from_user.id}/")
                queueDB.update(
                    {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}}
                )
                formatDB.update({cb.from_user.id: None})
                return
        elif "NO" in cb.data:
            new_file_name = (
                f"downloads/{str(cb.from_user.id)}/[@yashoswalyo]_merged.mkv"
            )
        await hardsub_and_upload(c, cb, new_file_name)

    elif cb.data.startswith("rename_zip_"):
        if "YES" in cb.data:
            await cb.message.edit("Send me a new file name for zip, you have 1 minute")
            try:
                new_name: Message = await c.listen(
                    chat_id=cb.message.chat.id, user_id=cb.from_user.id, timeout=60
                )
                if new_name.text:
                    new_file_name = (
                        f"downloads/{str(cb.from_user.id)}/" + new_name.text
                    )
                    await new_name.delete(True)
                else:
                    await new_name.reply_text(
                        "Invalid file name. Using default name."
                    )
                    new_file_name = (
                        f"downloads/{str(cb.from_user.id)}/[@yashoswalyo]_merged.zip"
                    )
            except asyncio.TimeoutError:
                await cb.message.edit("Time out")
                await cb.message.delete()
                await delete_all(root=f"downloads/{cb.from_user.id}/")
                queueDB.update(
                    {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}}
                )
                formatDB.update({cb.from_user.id: None})
                return
        elif "NO" in cb.data:
            new_file_name = (
                f"downloads/{str(cb.from_user.id)}/[@yashoswalyo]_merged.zip"
            )
        await zip_and_upload(c, cb, new_file_name)

    elif cb.data.startswith("rename_"):
        UserSettings(cb.from_user.id, cb.from_user.first_name)
        if "YES" in cb.data:
            await cb.message.edit(
                "Current filename: **[@yashoswalyo]_merged.mkv**\n\nSend me new file name without extension: You have 1 minute"
            )
            res: Message = await c.listen(
                cb.message.chat.id, filters=filters.text, timeout=150
            )
            if res.text:
                new_file_name = f"downloads/{str(cb.from_user.id)}/{res.text}.mkv"
                await res.delete(True)
            if len(queueDB.get(cb.from_user.id, {}).get("audios", [])) > 0:
                await mergeAudio(c, cb, new_file_name)
            elif any(sub is not None for sub in queueDB.get(cb.from_user.id, {}).get("subtitles", [])):
                await mergeSub(c, cb, new_file_name)
            else:
                await mergeNow(c, cb, new_file_name)

            return
        if "NO" in cb.data:
            new_file_name = (
                f"downloads/{str(cb.from_user.id)}/[@yashoswalyo]_merged.mkv"
            )
            if len(queueDB.get(cb.from_user.id, {}).get("audios", [])) > 0:
                await mergeAudio(c, cb, new_file_name)
            elif any(sub is not None for sub in queueDB.get(cb.from_user.id, {}).get("subtitles", [])):
                await mergeSub(c, cb, new_file_name)
            else:
                await mergeNow(c, cb, new_file_name)

    elif cb.data == "cancel":
        await delete_all(root=f"downloads/{cb.from_user.id}/")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        await cb.message.edit("Sucessfully Cancelled")
        await asyncio.sleep(5)
        await cb.message.delete(True)
        return

    elif cb.data.startswith("gUPcancel"):
        cmf = cb.data.split("/")
        chat_id, mes_id, from_usr = cmf[1], cmf[2], cmf[3]
        if int(cb.from_user.id) == int(from_usr):
            await c.answer_callback_query(
                cb.id, text="Going to Cancel . . . 🛠", show_alert=False
            )
            gDict[int(chat_id)].append(int(mes_id))
        else:
            await c.answer_callback_query(
                callback_query_id=cb.id,
                text="⚠️ Opps ⚠️ \n I Got a False Visitor 🚸 !! \n\n 📛 Stay At Your Limits !!📛",
                show_alert=True,
                cache_time=0,
            )
        await delete_all(root=f"downloads/{cb.from_user.id}/")
        queueDB.update(
            {cb.from_user.id: {"videos": [], "subtitles": [], "audios": []}})
        formatDB.update({cb.from_user.id: None})
        return

    elif cb.data == "help":
        await cb.message.edit(
            text="""**Follow These Steps:

1) Send me the custom thumbnail (optional).
2) Send two or more Your Videos Which you want to merge
3) After sending all files select merge options
4) Select rename if you want to give custom file name else press default**""",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Close 🔐", callback_data="close")]]
            )
        )
        return

    elif cb.data == "about":
        await cb.message.edit(
            text="""**Bot Name:** MERGE-BOT
**Developer:** Tongxin_Tech
**Version:** 1.0""",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Close 🔐", callback_data="close")]]
            )
        )
        return

    elif cb.data == "close":
        await cb.message.delete(True)
        try:
            await cb.message.reply_to_message.delete(True)
        except Exception:
            pass
        return

    elif cb.data.startswith("showFileName_"):
        id = int(cb.data.rsplit("_", 1)[-1])
        LOGGER.info(
            queueDB.get(cb.from_user.id)["videos"],
            queueDB.get(cb.from_user.id)["subtitles"],
        )
        sIndex = queueDB.get(cb.from_user.id)["videos"].index(id)
        m = await c.get_messages(chat_id=cb.message.chat.id, message_ids=id)
        if queueDB.get(cb.from_user.id)["subtitles"][sIndex] is None:
            try:
                await cb.message.edit(
                    text=f"File Name: {m.video.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "📜 Add Subtitle",
                                    callback_data=f"addSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            except BaseException:
                await cb.message.edit(
                    text=f"File Name: {m.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "📜 Add Subtitle",
                                    callback_data=f"addSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            return
        else:
            sMessId = queueDB.get(cb.from_user.id)["subtitles"][sIndex]
            s = await c.get_messages(chat_id=cb.message.chat.id, message_ids=sMessId)
            try:
                await cb.message.edit(
                    text=f"File Name: {m.video.file_name}\n\nSubtitles: {s.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove File",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "❌ Remove Subtitle",
                                    callback_data=f"removeSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            except BaseException:
                await cb.message.edit(
                    text=f"File Name: {m.document.file_name}\n\nSubtitles: {s.document.file_name}",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Remove File",
                                    callback_data=f"removeFile_{str(m.id)}",
                                ),
                                InlineKeyboardButton(
                                    "❌ Remove Subtitle",
                                    callback_data=f"removeSub_{str(sIndex)}",
                                ),
                            ],
                            [InlineKeyboardButton("🔙 Back", callback_data="back")],
                        ]
                    ),
                )
            return

    elif cb.data.startswith("addSub_"):
        sIndex = int(cb.data.split(sep="_")[1])
        vMessId = queueDB.get(cb.from_user.id)["videos"][sIndex]
        rmess = await cb.message.edit(
            text="Send me a subtitle file, you have 1 minute",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back", callback_data=f"showFileName_{vMessId}"
                        )
                    ]
                ]
            ),
        )
        subs: Message = await c.listen(
            cb.message.chat.id, filters=filters.document, timeout=60
        )
        if subs is not None:
            media = subs.document or subs.video
            if media.file_name.rsplit(".")[-1] not in "srt":
                await subs.reply_text(
                    text="Please go back first",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "🔙 Back", callback_data=f"showFileName_{vMessId}"
                                )
                            ]
                        ]
                    ),
                    quote=True,
                )
                return
            queueDB.get(cb.from_user.id)["subtitles"][sIndex] = subs.id
            await subs.reply_text(
                f"Added {subs.document.file_name}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔙 Back", callback_data=f"showFileName_{vMessId}"
                            )
                        ]
                    ]
                ),
                quote=True,
            )
            await rmess.delete(True)
            LOGGER.info("Added sub to list")
        return

    elif cb.data.startswith("removeSub_"):
        sIndex = int(cb.data.rsplit("_")[-1])
        vMessId = queueDB.get(cb.from_user.id)["videos"][sIndex]
        queueDB.get(cb.from_user.id)["subtitles"][sIndex] = None
        await cb.message.edit(
            text="Subtitle Removed Now go back or send next video",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back", callback_data=f"showFileName_{vMessId}"
                        )
                    ]
                ]
            ),
        )
        LOGGER.info("Sub removed from list")
        return

    elif cb.data == "back":
        await showQueue(c, cb)
        return

    elif cb.data.startswith("removeFile_"):
        sIndex = queueDB.get(cb.from_user.id)["videos"].index(
            int(cb.data.split("_", 1)[-1])
        )
        queueDB.get(cb.from_user.id)["videos"].remove(
            int(cb.data.split("_", 1)[-1]))
        await showQueue(c, cb)
        return

    elif cb.data == "tryotherbutton":
        await cb.answer()
        return

    elif cb.data.startswith('extract'):
        edata = cb.data.split('_')[1]
        media_mid = int(cb.data.split('_')[2])
        try:
            if edata == 'audio':
                LOGGER.info('audio')
                await streamsExtractor(c, cb, media_mid, exAudios=True)
            elif edata == 'subtitle':
                await streamsExtractor(c, cb, media_mid, exSubs=True)
            elif edata == 'video':
                await streamsExtractor(c, cb, media_mid, exVideo=True)
            elif edata == 'all':
                await streamsExtractor(c, cb, media_mid, exAudios=True, exSubs=True)
        except Exception as e:
            LOGGER.error(e)
