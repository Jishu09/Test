import datetime
import time

from motor.motor_asyncio import AsyncIOMotorClient

from bot.config import Config


class Database:
    def __init__(self, uri: str, db_name: str):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[db_name]

        self.users = self.db.users
        self.channels = self.db.channels
        self.fsub = self.db.fsub_channels
        self.banned = self.db.banned_users
        self.file_cache = self.db.file_cache
        self.settings = self.db.bot_settings
        self.broadcasts = self.db.broadcast_logs
        self.join_requests = self.db.join_requests
        self.tmdb_cache = self.db.tmdb_cache

    # ---------------- USERS ----------------
    async def add_user(self, user_id: int, name: str = "", username: str = ""):
        if await self.users.find_one({"_id": user_id}):
            return False
        await self.users.insert_one(
            {
                "_id": user_id,
                "name": name,
                "username": username,
                "joined_at": time.time(),
                "language": "en",
            }
        )
        return True

    async def is_user_exist(self, user_id: int) -> bool:
        return bool(await self.users.find_one({"_id": user_id}))

    async def total_users_count(self) -> int:
        return await self.users.count_documents({})

    async def get_all_users(self):
        return self.users.find({})

    async def delete_user(self, user_id: int):
        await self.users.delete_one({"_id": user_id})

    async def set_user_lang(self, user_id: int, lang: str):
        await self.users.update_one(
            {"_id": user_id}, {"$set": {"language": lang}}, upsert=True
        )

    async def get_user_lang(self, user_id: int) -> str:
        u = await self.users.find_one({"_id": user_id})
        return (u or {}).get("language", "en")

    # ---------------- BAN ----------------
    async def ban_user(self, user_id: int, reason: str = "No reason"):
        await self.banned.update_one(
            {"_id": user_id},
            {"$set": {"reason": reason, "banned_at": time.time()}},
            upsert=True,
        )

    async def unban_user(self, user_id: int):
        await self.banned.delete_one({"_id": user_id})

    async def is_banned(self, user_id: int) -> bool:
        return bool(await self.banned.find_one({"_id": user_id}))

    # ---------------- CHANNELS (caption-target channels connected to bot) ----------------
    async def add_channel(self, chat_id: int, title: str, added_by: int):
        existing = await self.channels.find_one({"_id": chat_id})
        if existing:
            await self.channels.update_one(
                {"_id": chat_id}, {"$set": {"title": title}}
            )
            return False
        await self.channels.insert_one(
            {
                "_id": chat_id,
                "title": title,
                "added_by": added_by,
                "added_at": time.time(),
                "caption": None,
                "auto_caption": True,
                "caption_reversal": False,
                "media_details": False,
                "caption_font": "normal",
                "media_filter": ["video", "document", "audio"],
                "custom_regex": {},
                "custom_buttons": None,
                "remove_words": [],
                "replace_words": {},
                "prefix": "",
                "suffix": "",
                "use_tmdb": True,
                "last_meta": {},
                "total_processed": 0,
            }
        )
        return True

    async def remove_channel(self, chat_id: int):
        await self.channels.delete_one({"_id": chat_id})

    async def get_channel(self, chat_id: int):
        return await self.channels.find_one({"_id": chat_id})

    async def get_all_channels(self):
        return self.channels.find({})

    async def total_channels_count(self) -> int:
        return await self.channels.count_documents({})

    async def set_caption(self, chat_id: int, caption: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"caption": caption}}, upsert=True
        )

    async def get_caption(self, chat_id: int) -> str:
        ch = await self.channels.find_one({"_id": chat_id})
        if ch and ch.get("caption"):
            return ch["caption"]
        return Config.DEFAULT_CAPTION

    async def get_caption_raw(self, chat_id: int):
        """Returns None if the admin hasn't set a custom caption yet."""
        ch = await self.channels.find_one({"_id": chat_id})
        return (ch or {}).get("caption")

    async def set_caption_font(self, chat_id: int, font: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"caption_font": font}}, upsert=True
        )

    async def toggle_caption_reversal(self, chat_id: int, state: bool):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"caption_reversal": state}}, upsert=True
        )

    async def toggle_media_details(self, chat_id: int, state: bool):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"media_details": state}}, upsert=True
        )

    async def toggle_use_tmdb(self, chat_id: int, state: bool):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"use_tmdb": state}}, upsert=True
        )

    # ---------------- TMDB TITLE CACHE ----------------
    # Keyed by a normalized "type:query" string so repeat episodes of the
    # same series never trigger a second network call, and restarts don't
    # lose the cache (unlike an in-memory dict).
    async def get_tmdb_cache(self, key: str):
        doc = await self.tmdb_cache.find_one({"_id": key})
        return doc["title"] if doc else None

    async def set_tmdb_cache(self, key: str, title: str):
        await self.tmdb_cache.update_one(
            {"_id": key},
            {"$set": {"title": title, "cached_at": time.time()}},
            upsert=True,
        )

    async def clear_tmdb_cache(self):
        result = await self.tmdb_cache.delete_many({})
        return result.deleted_count

    async def set_custom_buttons(self, chat_id: int, raw_text):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"custom_buttons": raw_text}}, upsert=True
        )

    async def add_remove_word(self, chat_id: int, word: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$addToSet": {"remove_words": word}}, upsert=True
        )

    async def clear_remove_words(self, chat_id: int):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"remove_words": []}}, upsert=True
        )

    async def add_replace_word(self, chat_id: int, old: str, new: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {f"replace_words.{old}": new}}, upsert=True
        )

    async def clear_replace_words(self, chat_id: int):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"replace_words": {}}}, upsert=True
        )

    async def set_prefix(self, chat_id: int, text: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"prefix": text}}, upsert=True
        )

    async def set_suffix(self, chat_id: int, text: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"suffix": text}}, upsert=True
        )

    async def toggle_auto_caption(self, chat_id: int, state: bool):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"auto_caption": state}}, upsert=True
        )

    async def set_media_filter(self, chat_id: int, media_types: list):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {"media_filter": media_types}}, upsert=True
        )

    async def update_last_meta(self, chat_id: int, meta: dict):
        """Store last successfully-parsed metadata fields to use as fallback."""
        clean = {k: v for k, v in meta.items() if v}
        if not clean:
            return
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {f"last_meta.{k}": v for k, v in clean.items()}}
        )
        await self.channels.update_one(
            {"_id": chat_id}, {"$inc": {"total_processed": 1}}
        )

    async def get_last_meta(self, chat_id: int) -> dict:
        ch = await self.channels.find_one({"_id": chat_id})
        return (ch or {}).get("last_meta", {})

    async def add_custom_regex(self, chat_id: int, field: str, pattern: str):
        await self.channels.update_one(
            {"_id": chat_id}, {"$set": {f"custom_regex.{field}": pattern}}, upsert=True
        )

    async def get_custom_regex(self, chat_id: int) -> dict:
        ch = await self.channels.find_one({"_id": chat_id})
        return (ch or {}).get("custom_regex", {})

    # ---------------- FORCE-SUB CHANNELS ----------------
    async def add_fsub_channel(self, chat_id: int, mode: str = "subscribe"):
        await self.fsub.update_one(
            {"_id": chat_id},
            {"$set": {"mode": mode, "added_at": time.time()}},
            upsert=True,
        )

    async def remove_fsub_channel(self, chat_id: int):
        await self.fsub.delete_one({"_id": chat_id})

    async def get_fsub_channels(self):
        return [doc async for doc in self.fsub.find({})]

    async def record_join_request(self, chat_id: int, user_id: int):
        await self.join_requests.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$set": {"requested_at": time.time()}},
            upsert=True,
        )

    async def has_join_request(self, chat_id: int, user_id: int) -> bool:
        return bool(
            await self.join_requests.find_one({"chat_id": chat_id, "user_id": user_id})
        )

    # ---------------- FILE DEDUP CACHE ----------------
    async def is_file_processed(self, file_unique_id: str) -> bool:
        return bool(await self.file_cache.find_one({"_id": file_unique_id}))

    async def mark_file_processed(self, file_unique_id: str, chat_id: int):
        try:
            await self.file_cache.insert_one(
                {
                    "_id": file_unique_id,
                    "chat_id": chat_id,
                    "processed_at": time.time(),
                }
            )
        except Exception:
            pass

    # ---------------- BOT SETTINGS ----------------
    async def get_setting(self, key: str, default=None):
        doc = await self.settings.find_one({"_id": key})
        return doc["value"] if doc else default

    async def set_setting(self, key: str, value):
        await self.settings.update_one(
            {"_id": key}, {"$set": {"value": value}}, upsert=True
        )

    async def is_maintenance(self) -> bool:
        return bool(await self.get_setting("maintenance_mode", False))

    async def set_maintenance(self, state: bool):
        await self.set_setting("maintenance_mode", state)

    # ---------------- STATS ----------------
    async def db_stats(self):
        stats = await self.db.command("dbstats")
        return {
            "storage_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
            "data_mb": round(stats.get("dataSize", 0) / (1024 * 1024), 2),
            "collections": stats.get("collections", 0),
        }


db = Database(Config.MONGO_URI, Config.DB_NAME)
