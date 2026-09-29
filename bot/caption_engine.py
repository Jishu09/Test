import asyncio
import difflib
import os
import re
import unicodedata
import logging
import aiohttp
from urllib.parse import quote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text normalization
#
# Uploaders/caption-writers very often use "fancy" Unicode fonts for style —
# e.g. 𝗧𝗶𝘁𝗹𝗲 instead of plain "Title" (Mathematical Alphanumeric Symbols).
# Those are different codepoints from normal ASCII letters, so a plain regex
# for "Title"/"Episode"/etc. would silently never match them. NFKC folds all
# of that back to plain ASCII, which is exactly what Unicode defines those
# codepoints' compatibility mapping to be — so this one call makes every
# label/pattern below work regardless of which "font" the caption used.
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    if not text:
        return text
    return unicodedata.normalize("NFKC", text)


# ---------------------------------------------------------------------------
# Regex patterns used to auto-detect metadata from a file name or caption.
# Each field has multiple fallback patterns tried in order.
# ---------------------------------------------------------------------------

SEASON_EP_PATTERNS = [
    r"[Ss](?P<season>\d{1,2})[\s._-]?[Ee](?P<episode>\d{1,3})",   # S01E02
    r"[Ss]eason[\s._-]?(?P<season>\d{1,2})[\s._-]?[Ee]p(?:isode)?[\s._-]?(?P<episode>\d{1,3})",
    r"(?P<season>\d{1,2})x(?P<episode>\d{1,3})",                  # 1x02
]

# Flexible label + separator: covers "Episode - 13", "Episode :- 11",
# "Episode : 11", "Episode: 11", "Episode- 11", "Ep: 11", "Ep:- 11",
# "Ep- 11" and bare "Episode 13" — any mix of spaces/colons/dashes/dots
# between the label and the number.
EPISODE_LABEL_PATTERN = r"\b(?:Episode|Ep)\b[\s:._-]*(?P<episode>\d{1,4})\b"
SEASON_LABEL_PATTERN = r"\bSeason\b[\s:._-]*(?P<season>\d{1,2})\b"

EPISODE_ONLY_PATTERNS = [
    EPISODE_LABEL_PATTERN,
    r"[Ee](?P<episode>\d{1,3})\b",
    r"(?:^|[\s._-])-\s?(?P<episode>\d{1,4})(?:[\s._-]|$)",        # Anime style: " - 12"
]

SEASON_ONLY_PATTERNS = [
    SEASON_LABEL_PATTERN,
    r"[Ss](?P<season>\d{1,2})(?![Ee\d])",
]

QUALITY_PATTERNS = [
    r"(?P<quality>2160p|4K|1080p|720p|576p|480p|360p|240p)",
]

LANGUAGE_PATTERNS = [
    r"\[?(?P<language>Bangla|Hindi|English|Tamil|Telugu|Multi[- ]?Audio|Dual[- ]?Audio|Malayalam|Kannada|Korean|Japanese)\]?",
]

YEAR_PATTERN = r"(?P<year>19\d{2}|20\d{2})"

RIP_PATTERNS = [
    r"(?P<source>WEB[- ]?DL|WEBRip|BluRay|BDRip|HDRip|DVDRip|HDTV|CAMRip|HDCAM)",
]

# Explicit "Label - value" caption lines, e.g.:
#   Title - Legend of Exorcism
#   Episode :- 11        Season: 01        Quality - 1080p
# These are the most reliable signal available (an uploader wrote it out
# by hand), so they always win over a generic filename/caption scan.
CAPTION_LABEL_PATTERN = re.compile(
    r"^\s*(?P<label>Title|Episode|Ep|Season|Quality|Audio|Language|Year)\b\s*[:.\-]*\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)


def parse_caption_labels(text: str) -> dict:
    """Parses explicitly-labeled lines out of a caption, e.g.
    'Title - X' / 'Episode :- 11' / 'Season: 01' / 'Quality - 1080p'
    / 'Audio - Hindi Dub'. Handles the fancy-Unicode-font labels used by
    many caption templates via normalize_text()."""
    result = {}
    if not text:
        return result
    for line in normalize_text(text).split("\n"):
        m = CAPTION_LABEL_PATTERN.match(line)
        if not m:
            continue
        label = m.group("label").lower()
        value = m.group("value").strip(" -:.|")
        if not value:
            continue
        if label in ("episode", "ep"):
            num = re.search(r"\d{1,4}", value)
            if num:
                result["episode"] = num.group()
        elif label == "season":
            num = re.search(r"\d{1,2}", value)
            if num:
                result["season"] = num.group()
        elif label == "quality":
            qm = re.search(QUALITY_PATTERNS[0], value, re.IGNORECASE)
            if qm:
                result["quality"] = qm.group("quality")
        elif label in ("audio", "language"):
            result["language"] = value
        elif label == "title":
            result["title"] = value
        elif label == "year":
            ym = re.search(YEAR_PATTERN, value)
            if ym:
                result["year"] = ym.group("year")
    return result


# Every one of these gets stripped out before a filename is turned into a
# search query — anything left over here used to leak straight into TMDB
# queries (e.g. "480p" wasn't in the old list at all) and produce garbage
# or mismatched results.
NOISE_TOKENS = (
    r"S\d{1,2}E\d{1,3}|S\d{1,2}|Season\s?\d+|E\d{1,3}|Episode\s?\d+|Ep\s?\d+|"
    r"2160p|1080p|720p|576p|480p|360p|240p|4K|8K|2K|HDR|"
    r"WEB[- ]?DL|WEBRip|BluRay|BDRip|HDRip|DVDRip|HDTV|CAMRip|HDCAM|"
    r"x264|x265|H\.?264|H\.?265|HEVC|AVC|10[- ]?bit|"
    r"AAC(?:\d\.\d)?|DDP?\d\.\d|EAC3|AC3|"
    r"Dual[- ]?Audio|Multi[- ]?Audio|Hindi|English|Bangla|Tamil|Telugu|"
    r"Malayalam|Kannada|Korean|Japanese|Dubbed|Dub|ESub|Subs?|UNCUT|"
    r"REMASTERED|PROPER|REPACK|EXTENDED|IMAX|NF|AMZN|DSNP|HS"
)


def _clean(text: str) -> str:
    text = re.sub(r"[._]", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


# Filenames that carry no real info at all — either a generic placeholder
# word (often one we generated ourselves, e.g. "video_12345" for a file
# Telegram gave no name to) or a bare timestamp/ID. A title built purely
# from one of these is worse than no title, since it would block the
# caption-text fallback from ever running.
GENERIC_STEMS = {
    "video", "vid", "img", "image", "movie", "file", "clip", "media",
    "download", "untitled", "new", "audio", "document", "photo",
}


def _is_low_quality_title(name: str) -> bool:
    if not name:
        return True
    words = [w for w in re.split(r"[\s._-]+", name.strip()) if w]
    non_numeric_words = [w for w in words if not w.isdigit()]
    if not non_numeric_words:
        return True  # e.g. "20240115 143022" — pure timestamp/ID
    if len(non_numeric_words) == 1 and non_numeric_words[0].lower() in GENERIC_STEMS:
        return True  # e.g. "video 12345", "IMG 1234"
    return False


def _strip_span(text: str, span) -> str:
    """Blanks out exactly the matched characters (replaced with a space so
    word boundaries on either side survive), used to remove metadata that
    was already extracted from wherever it actually sits in the string —
    start, middle, or end — instead of only matching a fixed noise-word
    list. This is what correctly handles a title that sits *after* the
    metadata (common in anime naming) or has a bare episode marker like
    "Naruto - 05" that no generic word-list could recognize as noise."""
    if not span:
        return text
    start, end = span
    return text[:start] + " " + text[end:]


def extract_title(filename: str, consumed_spans: list = None) -> str:
    """Extracts a clean search query from the filename (or caption line) for
    TMDB, and as the plain-regex fallback title when TMDB is off/unavailable
    /unconfident. `consumed_spans` are exact character ranges already
    identified as season/episode/quality/language/year/source — removing
    those directly is what correctly handles metadata sitting anywhere in
    the string, not just cases covered by the static noise-word list."""
    name = os.path.splitext(filename)[0]
    name = normalize_text(name)

    # 1. Remove exactly the spans already identified as other metadata
    # fields (rightmost first so earlier offsets stay valid). This MUST
    # happen before any other transformation that could shift character
    # positions (bracket stripping, etc.) — the spans were computed
    # against this exact extension-stripped, NFKC-normalized string.
    for span in sorted(consumed_spans or [], key=lambda s: -s[0]):
        name = _strip_span(name, span)

    # 2. Remove brackets, tags, and channel mentions completely
    name = re.sub(r"\[.*?\]|\(.*?\)|\{.*?\}|@[\w]+", "", name)

    # 3. Clean up dots and underscores
    name = _clean(name)

    # 4. Aggressively remove obvious metadata/quality/codec/audio tags that
    # aren't tracked as a specific field (x264, ESub, WEB-DL, etc.)
    name = re.sub(rf"(?i)\b({NOISE_TOKENS})\b", "", name)

    # 5. Strip a trailing release-group tag, e.g. "Movie Name-RARBG"
    name = re.sub(r"-[A-Za-z0-9]{2,15}$", "", name)

    # 6. Final cleanup
    name = re.sub(r"\s{2,}", " ", name).strip(" -_.[](){}:|")

    if not name or name.lower() in ("episode", "ep", "season", "series", "movie", "anime") or _is_low_quality_title(name):
        return None

    return name


# ---------------------------------------------------------------------------
# TMDB resolution
#
# Design goals:
#   1. Speed  — a single shared aiohttp session (not one per request) plus a
#      MongoDB-backed cache keyed by the cleaned query, so the *same* series
#      never triggers more than one network call, ever (survives restarts).
#   2. Accuracy — search /search/tv when a season/episode was detected and
#      /search/movie otherwise, instead of /search/multi, so a TV episode
#      can no longer match an unrelated movie (this was exactly how
#      "Demon Slayer ... Episode 1" turned into "... Infinity Castle").
#      A result is only accepted if it's textually close enough to the
#      query, *and* doesn't add/drop a significant number of words versus
#      the query — that second check specifically stops near-neighbor
#      titles like "Naruto" -> "Naruto Shippuden" (a different, separate
#      show) from being silently swapped in. Anything that doesn't clear
#      both bars keeps the regex-cleaned title instead of trusting a
#      low-confidence guess.
# ---------------------------------------------------------------------------

_session: aiohttp.ClientSession = None
_session_lock = asyncio.Lock()

MATCH_THRESHOLD = 0.62
WORD_COUNT_PENALTY = 0.10  # subtracted per extra/missing significant word


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        async with _session_lock:
            if _session is None or _session.closed:
                timeout = aiohttp.ClientTimeout(total=4)
                _session = aiohttp.ClientSession(timeout=timeout)
    return _session


async def close_tmdb_session():
    global _session
    if _session and not _session.closed:
        await _session.close()


def _normalize(text: str) -> str:
    text = normalize_text(text)
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _score(query_norm: str, candidate_norm: str) -> float:
    if query_norm == candidate_norm:
        return 1.0
    ratio = difflib.SequenceMatcher(None, query_norm, candidate_norm).ratio()
    q_words = query_norm.split()
    c_words = candidate_norm.split()
    word_diff = abs(len(q_words) - len(c_words))
    # A different word count is a strong signal of a genuinely different
    # title sharing a common prefix — e.g. "Naruto" vs "Naruto Shippuden",
    # or a TV title vs a same-franchise movie with one extra subtitle word.
    return ratio - (WORD_COUNT_PENALTY * word_diff)


def _best_match(query: str, results: list, is_series: bool, year: str = None):
    norm_query = _normalize(query)
    best, best_score = None, 0.0
    for res in results[:5]:
        candidate = res.get("name") if is_series else res.get("title")
        if not candidate:
            continue
        score = _score(norm_query, _normalize(candidate))
        if year:
            date = res.get("first_air_date") or res.get("release_date") or ""
            if date.startswith(str(year)):
                score += 0.1  # small nudge toward a matching release year
        if score > best_score:
            best, best_score = candidate, score
    return best, best_score


async def resolve_title(query: str, api_key: str, is_series: bool = False, year: str = None) -> str:
    """Returns the best available title: a validated TMDB match if confident,
    otherwise the original cleaned query untouched. Never raises, and never
    blocks longer than a few seconds even on network trouble."""
    if not query:
        return query
    if not api_key:
        return query

    cache_key = f"{'tv' if is_series else 'movie'}:{_normalize(query)}"
    try:
        cached = await _cache_get(cache_key)
        if cached is not None:
            return cached
    except Exception as e:
        logger.warning(f"TMDB cache read failed: {e}")

    endpoint = "tv" if is_series else "movie"
    url = f"https://api.themoviedb.org/3/search/{endpoint}?api_key={api_key}&query={quote(query)}"
    if year:
        url += f"&{'first_air_date_year' if is_series else 'primary_release_year'}={year}"

    resolved = query
    try:
        session = await _get_session()
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results") or []
                if results:
                    best, score = _best_match(query, results, is_series, year)
                    if best and score >= MATCH_THRESHOLD:
                        resolved = best
            elif resp.status == 401:
                logger.warning("TMDB API key rejected (401) — check TMDB_API_KEY.")
    except asyncio.TimeoutError:
        logger.warning(f"TMDB request timed out for '{query}'.")
    except Exception as e:
        logger.warning(f"TMDB API fetch failed for '{query}': {e}")

    try:
        await _cache_set(cache_key, resolved)
    except Exception as e:
        logger.warning(f"TMDB cache write failed: {e}")

    return resolved


async def _cache_get(key: str):
    from bot.database import db

    return await db.get_tmdb_cache(key)


async def _cache_set(key: str, title: str):
    from bot.database import db

    await db.set_tmdb_cache(key, title)


def _scan(search_space: str, data: dict, consumed_spans: list):
    """Fills any still-missing field in `data` by scanning `search_space`,
    and records the matched span of each hit into `consumed_spans` so
    extract_title() can surgically remove exactly that text later."""
    if not data["season"] or not data["episode"]:
        for pattern in SEASON_EP_PATTERNS:
            m = re.search(pattern, search_space, re.IGNORECASE)
            if m:
                if not data["season"]:
                    data["season"] = m.group("season")
                if not data["episode"]:
                    data["episode"] = m.group("episode")
                consumed_spans.append(m.span())
                break

    if not data["episode"]:
        for pattern in EPISODE_ONLY_PATTERNS:
            m = re.search(pattern, search_space, re.IGNORECASE)
            if m:
                data["episode"] = m.group("episode")
                consumed_spans.append(m.span("episode"))
                break

    if not data["season"]:
        for pattern in SEASON_ONLY_PATTERNS:
            m = re.search(pattern, search_space, re.IGNORECASE)
            if m:
                data["season"] = m.group("season")
                consumed_spans.append(m.span("season"))
                break

    if not data["quality"]:
        for pattern in QUALITY_PATTERNS:
            m = re.search(pattern, search_space, re.IGNORECASE)
            if m:
                data["quality"] = m.group("quality")
                consumed_spans.append(m.span())
                break

    if not data["language"]:
        for pattern in LANGUAGE_PATTERNS:
            m = re.search(pattern, search_space, re.IGNORECASE)
            if m:
                data["language"] = m.group("language").replace("-", " ").replace("_", " ")
                consumed_spans.append(m.span())
                break

    if not data["year"]:
        m = re.search(YEAR_PATTERN, search_space)
        if m:
            data["year"] = m.group("year")
            consumed_spans.append(m.span())

    if not data["source"]:
        for pattern in RIP_PATTERNS:
            m = re.search(pattern, search_space, re.IGNORECASE)
            if m:
                data["source"] = m.group("source")
                consumed_spans.append(m.span())
                break


def parse_filename(filename: str, custom_regex: dict = None, fallback_text: str = None) -> dict:
    """Extract season, episode, quality, language, year, source, title.

    Tries the filename first. Filenames get truncated in Telegram's UI and
    often bury season/episode/quality near the end where they're easy to
    miss visually, but that doesn't affect regex matching — the *actual*
    fallback this handles is uploaders who simply never put that info in
    the filename at all and instead wrote it into the file's caption
    (`fallback_text`), in all sorts of label styles ("Episode - 13",
    "Ep: 11", plain "S01E06", etc., possibly in a fancy Unicode font).
    Whatever the filename can't determine, the caption is checked next —
    first for explicit "Label - value" lines (most reliable), then with the
    same generic pattern scan used on the filename.
    """
    custom_regex = custom_regex or {}
    data = {
        "season": None,
        "episode": None,
        "quality": None,
        "language": None,
        "year": None,
        "source": None,
        "title": None,
        "raw_title": None,  # Backup of regex title for smart caching
    }

    filename_norm = normalize_text(filename)
    consumed_spans = []

    # Allow per-channel custom regex overrides for any field — checked
    # against filename + caption together since an admin's custom pattern
    # might target either.
    combined_for_custom = filename_norm + "\n" + normalize_text(fallback_text or "")
    for field, pattern in custom_regex.items():
        try:
            m = re.search(pattern, combined_for_custom, re.IGNORECASE)
            if m:
                groupdict = m.groupdict()
                data[field] = groupdict.get(field) or (m.group(1) if m.groups() else m.group(0))
        except re.error:
            continue

    # 1. Scan the filename.
    _scan(filename_norm, data, consumed_spans)

    # Title from the filename comes first too — the caption is only a
    # fallback when the filename genuinely doesn't yield anything usable
    # (e.g. "video_12345.mkv"), never an override for a filename that
    # already has a clean title.
    data["title"] = extract_title(filename, consumed_spans)

    # 2. Whatever's still missing, try the caption's explicit labeled lines
    # first (most reliable — an uploader wrote it by hand).
    if fallback_text and not all([data["season"], data["episode"], data["quality"], data["title"]]):
        labeled = parse_caption_labels(fallback_text)
        for key, val in labeled.items():
            if not data.get(key):
                data[key] = val

    # 3. Still missing something? Fall back to a generic pattern scan of
    # the caption text too (covers un-labeled captions that just repeat
    # filename-style info, e.g. "Show Name S02E07 1080p").
    if fallback_text and not all([data["season"], data["episode"], data["quality"]]):
        caption_norm = normalize_text(fallback_text)
        caption_spans = []
        _scan(caption_norm, data, caption_spans)

    if data["season"]:
        data["season"] = str(int(data["season"])).zfill(2)
    if data["episode"]:
        data["episode"] = str(int(data["episode"])).zfill(2)

    if not data["title"] and fallback_text:
        # Filename gave nothing usable at all (e.g. "video_12345.mkv") and
        # the caption had no explicit "Title - X" line either — last
        # resort: use the first caption line that ISN'T itself a
        # metadata label line (Episode/Season/Quality/...), so we don't
        # accidentally turn "Episode :- 11" into the title.
        for line in normalize_text(fallback_text).split("\n"):
            line = line.strip()
            if not line or CAPTION_LABEL_PATTERN.match(line):
                continue
            candidate = extract_title(line, [])
            if candidate:
                data["title"] = candidate
                break

    return data


def merge_with_fallback(parsed: dict, last_meta: dict) -> dict:
    """Fill missing fields using the channel's last successfully-detected metadata."""
    merged = dict(parsed)
    for key, val in (last_meta or {}).items():
        if not merged.get(key):
            merged[key] = val
    return merged


def human_size(size_bytes: int) -> str:
    if not size_bytes:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"


def human_duration(seconds: int) -> str:
    if not seconds:
        return "N/A"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_wish() -> str:
    import datetime
    import pytz

    from bot.config import Config

    try:
        tz = pytz.timezone(Config.TIMEZONE)
    except Exception:
        tz = pytz.utc
    hour = datetime.datetime.now(tz).hour
    if 5 <= hour < 12:
        return "Good Morning"
    if 12 <= hour < 17:
        return "Good Afternoon"
    if 17 <= hour < 21:
        return "Good Evening"
    return "Good Night"


def apply_remove_words(text: str, words: list) -> str:
    for w in words or []:
        if not w:
            continue
        text = re.sub(re.escape(w), "", text, flags=re.IGNORECASE)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def apply_replace_words(text: str, mapping: dict) -> str:
    for old, new in (mapping or {}).items():
        if not old:
            continue
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    return text


def apply_prefix_suffix(text: str, prefix: str = "", suffix: str = "") -> str:
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(text)
    if suffix:
        parts.append(suffix)
    return "\n\n".join(p for p in parts if p)


def reverse_caption(text: str) -> str:
    lines = [l for l in text.split("\n")]
    return "\n".join(reversed(lines))


_FONT_MAP = {
    "normal": (lambda t: t),
    "bold": (lambda t: f"**{t}**"),
    "italic": (lambda t: f"__{t}__"),
    "mono": (lambda t: f"`{t}`"),
    "underline": (lambda t: f"--{t}--"),
}


def apply_font(text: str, font: str) -> str:
    fn = _FONT_MAP.get((font or "normal").lower(), _FONT_MAP["normal"])
    # Apply per-line so multi-line captions keep correct Markdown formatting.
    return "\n".join(fn(line) if line.strip() else line for line in text.split("\n"))


def build_caption(template: str, meta: dict) -> str:
    """meta is a fully-populated dict of every placeholder value."""
    values = {
        "filename": meta.get("filename", ""),
        "filesize": human_size(meta.get("filesize", 0)),
        "duration": human_duration(meta.get("duration", 0)),
        "channel": meta.get("channel", ""),
        "extension": meta.get("extension", ""),
        "ext": meta.get("extension", ""),
        "season": meta.get("season") or "",
        "episode": meta.get("episode") or "",
        "quality": meta.get("quality") or "",
        "language": meta.get("language") or "",
        "year": meta.get("year") or "",
        "source": meta.get("source") or "",
        "title": meta.get("title") or meta.get("filename", ""),
        "height": meta.get("height") or "",
        "width": meta.get("width") or "",
        "resolution": (
            f"{meta.get('width')}x{meta.get('height')}"
            if meta.get("width") and meta.get("height")
            else ""
        ),
        "mime_type": meta.get("mime_type") or "",
        "artist": meta.get("artist") or "",
        "caption": meta.get("caption") or "",
        "html_caption": meta.get("html_caption") or meta.get("caption") or "",
        "wish": get_wish(),
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        # Unknown placeholder in template — do a safe partial substitution.
        out = template
        for k, v in values.items():
            out = out.replace("{" + k + "}", str(v))
        return out
