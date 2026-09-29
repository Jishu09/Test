import logging
import os
import sys
from collections import defaultdict
from logging.handlers import RotatingFileHandler

from Vivian.Function.msg_utils import MakeButtons

"""Some Constants"""
UPLOAD_AS_DOC = {}
UPLOAD_DESTINATION = {}

FINISHED_PROGRESS_STR = os.environ.get("FINISHED_PROGRESS_STR", "█")
UN_FINISHED_PROGRESS_STR = os.environ.get("UN_FINISHED_PROGRESS_STR", "░")
EDIT_SLEEP_TIME_OUT = 10
gDict = defaultdict(lambda: [])
queueDB = {}
formatDB = {}
replyDB = {}

VIDEO_EXTENSIONS = ["mkv", "mp4", "webm", "ts", "wav", "mov"]
AUDIO_EXTENSIONS = ["aac", "ac3", "eac3", "m4a", "mka", "thd", "dts", "mp3"]
SUBTITLE_EXTENSIONS = ["srt", "ass", "mka", "mks"]

w = open("mergebotlog.txt", "w")
w.truncate(0)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            "mergebotlog.txt",
            maxBytes=50000000,
            backupCount=10),
        logging.StreamHandler(
            sys.stdout),
    ],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

LOGGER = logging.getLogger(__name__)
BROADCAST_MSG = """
**Total: {}
Done: {}**
"""
bMaker = MakeButtons()
