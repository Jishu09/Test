from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, Message, CallbackQuery

from bot.database import db
from utils.buttons import success_btn

def register(app: Client):
    @app.on_message(filters.command("lang") & filters.private)
    async def lang_cmd(client: Client, message: Message):
        current = await db.get_user_lang(message.from_user.id)
        
        # Language Options
        langs = [
            ("en", "🇬🇧 English"),
            ("hi", "🇮🇳 Hindi"),
            ("bn", "🇧🇩 Bangla"),
            ("es", "🇪🇸 Spanish"),
            ("pt", "🇧🇷 Portuguese"),
        ]
        
        buttons = []
        for code, name in langs:
            # Add checkmark if selected
            label = name + (" ✓" if current == code else "")
            buttons.append(success_btn(label, callback_data=f"lang_{code}"))
        
        # Creating a nice layout (2 buttons per row)
        markup = InlineKeyboardMarkup([
            [buttons[0], buttons[1]],
            [buttons[2], buttons[3]],
            [buttons[4]]
        ])
        
        await message.reply_text("🌐 **Choose your interface language:**", reply_markup=markup)

    @app.on_callback_query(filters.regex(r"^lang_(en|hi|bn|es|pt)$"))
    async def lang_cb(client: Client, cq: CallbackQuery):
        lang = cq.matches[0].group(1)
        await db.set_user_lang(cq.from_user.id, lang)
        
        # Confirmation messages
        alerts = {
            "en": "✅ Language set to English.",
            "hi": "✅ भाषा हिंदी में सेट की गई।",
            "bn": "✅ ভাষা বাংলা করা হয়েছে।",
            "es": "✅ Idioma configurado en español.",
            "pt": "✅ Idioma definido para português."
        }
        
        await cq.answer(alerts.get(lang), show_alert=True)
