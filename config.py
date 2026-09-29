import os


class Config(object):
    API_HASH = os.environ.get("API_HASH", "a510b57f3faf99742315e2bd7a91b12e")
    BOT_TOKEN = os.environ.get(
        "BOT_TOKEN",
        "8866470219:AAGsrszt9TpxZRG6TwMMepZlHnVQtFoJfL0")
    GOFILE_TOKEN = os.environ.get(
        "GOFILE_TOKEN",
        "of3577A2Aw1HbmUkJs68PbRhmWLqvasa")
    TELEGRAM_API = os.environ.get("TELEGRAM_API", "3950715")
    OWNER = os.environ.get("OWNER", "8810409641")
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "bot_username")
    PASSWORD = os.environ.get("PASSWORD", "test")
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "mongodb+srv://hohavir622_db_user:nRwZ6iiUohz3rHXg@cluster0.0zncemp.mongodb.net/?appName=Cluster0")
    LOGCHANNEL = os.environ.get("LOGCHANNEL", "-1003947134631")
    USER_SESSION_STRING = os.environ.get("USER_SESSION_STRING", None)
    PORT = int(os.environ.get("PORT", "8080"))

    FFCODE_1080 = os.environ.get(
        "FFCODE_1080",
        'ffmpeg -i {} -preset veryfast -c:v libx264 -crf 24 -vf "scale=1920:1080" -c:a libopus -b:a 128k -map 0 -progress {} {} -y')
    FFCODE_720 = os.environ.get(
        "FFCODE_720",
        'ffmpeg -i {} -preset veryfast -c:v libx264 -crf 26 -vf "scale=1280:720" -c:a libopus -b:a 96k -map 0 -progress {} {} -y')
    FFCODE_480 = os.environ.get(
        "FFCODE_480",
        'ffmpeg -i {} -preset veryfast -c:v libx264 -crf 28 -vf "scale=854:480" -c:a libopus -b:a 64k -map 0 -progress {} {} -y')
    FFCODE_360 = os.environ.get(
        "FFCODE_360",
        'ffmpeg -i {} -preset veryfast -c:v libx264 -crf 28 -vf "scale=640:360" -c:a libopus -b:a 48k -map 0 -progress {} {} -y')
