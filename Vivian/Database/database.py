from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config import Config
from main import LOGGER


class Database(object):
    client = MongoClient(Config.DATABASE_URL)
    mergebot = client.MergeBot


async def addUser(uid, fname, lname):
    try:
        userDetails = {
            "_id": uid,
            "name": f"{fname} {lname}",
        }
        Database.mergebot.users.insert_one(userDetails)
        LOGGER.info(f"New user added id={uid}\n{fname} {lname} \n")
    except DuplicateKeyError:
        LOGGER.info(f"Duplicate Entry Found for id={uid}\n{fname} {lname} \n")
    return


async def broadcast():
    a = Database.mergebot.mergeSettings.find({})
    return a


async def allowUser(uid, fname, lname):
    try:
        Database.mergebot.allowedUsers.insert_one(
            {
                "_id": uid,
            }
        )
    except DuplicateKeyError:
        LOGGER.info(f"Duplicate Entry Found for id={uid}\n{fname} {lname} \n")
    return


async def allowedUser(uid):
    a = Database.mergebot.allowedUsers.find_one({"_id": uid})
    try:
        if uid == a["_id"]:
            return True
    except TypeError:
        return False


async def saveThumb(uid, fid):
    try:
        Database.mergebot.thumbnail.insert_one({"_id": uid, "thumbid": fid})
    except DuplicateKeyError:
        Database.mergebot.thumbnail.replace_one({"_id": uid}, {"thumbid": fid})


async def delThumb(uid):
    Database.mergebot.thumbnail.delete_many({"_id": uid})
    return True


async def getThumb(uid):
    res = Database.mergebot.thumbnail.find_one({"_id": uid})
    return res["thumbid"]


async def deleteUser(uid):
    Database.mergebot.mergeSettings.delete_many({"_id": uid})


def getUserMergeSettings(uid: int):
    try:
        res_cur = Database.mergebot.mergeSettings.find_one({"_id": uid})
        return res_cur
    except Exception as e:
        LOGGER.info(e)
        return None


def setUserMergeSettings(
        uid: int,
        name: str,
        edit_metadata,
        banned,
        allowed,
        thumbnail):
    if uid:
        try:
            Database.mergebot.mergeSettings.insert_one(
                document={
                    "_id": uid,
                    "name": name,
                    "user_settings": {
                        "edit_metadata": edit_metadata,
                    },
                    "isAllowed": allowed,
                    "isBanned": banned,
                    "thumbnail": thumbnail,
                }
            )
        except Exception:
            Database.mergebot.mergeSettings.replace_one(
                filter={"_id": uid},
                replacement={
                    "name": name,
                    "user_settings": {
                        "edit_metadata": edit_metadata,
                    },
                    "isAllowed": allowed,
                    "isBanned": banned,
                    "thumbnail": thumbnail,
                },
            )


def enableMetadataToggle(uid: int, value: bool):
    try:
        Database.mergebot.mergeSettings.update_one(
            {"_id": uid},
            {"$set": {"user_settings.edit_metadata": value}}
        )
    except Exception as e:
        LOGGER.error(f"Error updating metadata toggle: {e}")


def disableMetadataToggle(uid: int, value: bool):
    try:
        Database.mergebot.mergeSettings.update_one(
            {"_id": uid},
            {"$set": {"user_settings.edit_metadata": value}}
        )
    except Exception as e:
        LOGGER.error(f"Error updating metadata toggle: {e}")


def getEncodeSettings(uid: int):
    try:
        res_cur = Database.mergebot.encodeSettings.find_one({"_id": uid})
        if res_cur is None:

            return {
                "_id": uid,
                "crf": "27",
                "codec": "libx264",
                "resolution": "854x480",
                "preset": "veryfast",
                "audio_b": "48k"}
        return res_cur
    except Exception as e:
        LOGGER.info(e)
        return {
            "_id": uid,
            "crf": "27",
            "codec": "libx264",
            "resolution": "854x480",
            "preset": "veryfast",
            "audio_b": "48k"}


def setEncodeSettings(uid: int, settings: dict):
    if uid:
        try:
            settings["_id"] = uid
            Database.mergebot.encodeSettings.replace_one(
                {"_id": uid},
                settings,
                upsert=True
            )
            LOGGER.info(f"Encode settings for user {uid} updated")
        except Exception as e:
            LOGGER.info(e)


def getMetadata(uid: int):
    try:
        res_cur = Database.mergebot.metadataSettings.find_one({"_id": uid})
        if res_cur is None:
            return {"_id": uid}
        return res_cur
    except Exception as e:
        LOGGER.info(e)
        return {"_id": uid}


def setMetadata(uid: int, settings: dict):
    if uid:
        try:
            settings["_id"] = uid
            Database.mergebot.metadataSettings.replace_one(
                {"_id": uid},
                settings,
                upsert=True
            )
            LOGGER.info(f"Metadata settings for user {uid} updated")
        except Exception as e:
            LOGGER.info(e)
