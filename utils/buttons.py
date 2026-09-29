"""
Colored inline-keyboard button helpers.

Bot API 9.4 / Kurigram-Pyrofork's `style` field on InlineKeyboardButton takes
a `pyrogram.enums.ButtonStyle` member — NOT a plain string. Passing a raw
string like "primary" doesn't raise an error (it's just stored on the
object), so the button silently renders with no color instead of failing
loudly. That was the actual bug: this file now maps our string constants to
the real enum members before ever touching InlineKeyboardButton.

`Button` below also auto-picks a color from the button's text (mirroring
the working logic from another bot) for any call site that doesn't force an
explicit style — so new buttons get sensible colors without every call site
having to pick one.
"""

import re
import logging

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

try:
    from pyrogram.enums import ButtonStyle
    _HAS_STYLE = True
except ImportError:
    ButtonStyle = None
    _HAS_STYLE = False

PRIMARY = "primary"   # blue
SUCCESS = "success"   # green
DANGER = "danger"     # red
DEFAULT = "default"   # plain gray

_STYLE_MAP = {}
if _HAS_STYLE:
    _STYLE_MAP = {
        PRIMARY: ButtonStyle.PRIMARY,
        SUCCESS: ButtonStyle.SUCCESS,
        DANGER: ButtonStyle.DANGER,
        DEFAULT: ButtonStyle.DEFAULT,
    }

_DANGER_WORDS = ("close", "cancel", "delete", "ban", "❌", "✖️", "back", "⬅️", "🔙",
                 "del", "remove", "🗑", "➖", "off", "clear", "reset", "no,", "disconnect")
_SUCCESS_WORDS = ("done", "download", "✅", "📥", "success", "add", "➕", "start",
                   "joined", " on", "active", "connect", "yes,", "save", "confirm")
_DEFAULT_WORDS = ("help", "about", "developer", "info", "settings", "preview", "prev",
                   "next", "◀", "▶", "noop", "refresh", "clean", "manage", "format")


def _auto_style(text: str):
    lower_text = text.lower()
    if any(w in lower_text for w in _DANGER_WORDS):
        return ButtonStyle.DANGER
    if any(w in lower_text for w in _SUCCESS_WORDS):
        return ButtonStyle.SUCCESS
    if any(w in lower_text for w in _DEFAULT_WORDS):
        return ButtonStyle.DEFAULT
    return ButtonStyle.PRIMARY


def _resolve_style(text: str, style):
    """style may be one of our string constants, a raw ButtonStyle member,
    or None (meaning: auto-detect from the button text)."""
    if not _HAS_STYLE:
        return None
    if style is None:
        return _auto_style(text)
    if isinstance(style, str):
        return _STYLE_MAP.get(style)
    return style  # already a ButtonStyle member


def _safe_button(text: str, style=None, **kwargs) -> InlineKeyboardButton:
    """Creates an InlineKeyboardButton, applying a real ButtonStyle enum
    member. Falls back to a plain button if the installed Pyrofork build
    doesn't support `style` at all (older versions), so this never crashes."""
    enum_style = _resolve_style(text, style)
    if enum_style is not None:
        try:
            return InlineKeyboardButton(text=text, style=enum_style, **kwargs)
        except TypeError:
            logger.debug(f"Colored buttons not supported by current Pyrofork build; falling back for: {text}")
    return InlineKeyboardButton(text=text, **kwargs)


def primary_btn(text: str, **kwargs) -> InlineKeyboardButton:
    return _safe_button(text, style=PRIMARY, **kwargs)


def success_btn(text: str, **kwargs) -> InlineKeyboardButton:
    return _safe_button(text, style=SUCCESS, **kwargs)


def danger_btn(text: str, **kwargs) -> InlineKeyboardButton:
    return _safe_button(text, style=DANGER, **kwargs)


def default_btn(text: str, **kwargs) -> InlineKeyboardButton:
    return _safe_button(text, style=DEFAULT, **kwargs)


def plain_btn(text: str, **kwargs) -> InlineKeyboardButton:
    """No style is forced — color is auto-detected from the button text."""
    return _safe_button(text, style=None, **kwargs)


class Button(InlineKeyboardButton):
    """Drop-in InlineKeyboardButton with the same semantic auto-coloring
    behaviour as the reference implementation, for call sites that want to
    build buttons directly instead of via the helper functions above."""

    def __init__(self, text, callback_data=None, url=None, web_app=None,
                 login_url=None, user_id=None, switch_inline_query=None,
                 switch_inline_query_current_chat=None, callback_game=None,
                 requires_password=None, pay=None, copy_text=None,
                 icon_custom_emoji_id=None, style=None):
        enum_style = _resolve_style(text, style)
        kwargs = dict(
            callback_data=callback_data, url=url, web_app=web_app,
            login_url=login_url, user_id=user_id,
            switch_inline_query=switch_inline_query,
            switch_inline_query_current_chat=switch_inline_query_current_chat,
            callback_game=callback_game, requires_password=requires_password,
            pay=pay, copy_text=copy_text,
            icon_custom_emoji_id=icon_custom_emoji_id,
        )
        try:
            super().__init__(text, style=enum_style, **kwargs)
        except TypeError:
            super().__init__(text, **kwargs)


# Regex to capture [Text][buttonurl:https://...]
BUTTON_TOKEN = re.compile(r"\[(?P<text>[^\[\]]+?)\]\[buttonurl:(?P<url>[^\[\]]+?)\]", re.IGNORECASE)


def parse_custom_buttons(raw_text: str):
    """
    Parses admin-defined button templates like:
    [Button 1][buttonurl:https://a.com] && [Button 2][buttonurl:https://b.com]

    Multiple buttons on one line (separated by '&&') land in the same row;
    each new line starts a new row.
    """
    if not raw_text:
        return None

    rows = []
    for line in raw_text.strip().split("\n"):
        row = []
        for chunk in line.split("&&"):
            m = BUTTON_TOKEN.search(chunk)
            if m:
                btn_text = m.group("text").strip()
                btn_url = m.group("url").strip()
                row.append(plain_btn(text=btn_text, url=btn_url))

        if row:
            rows.append(row)

    if not rows:
        return None

    return InlineKeyboardMarkup(rows)
