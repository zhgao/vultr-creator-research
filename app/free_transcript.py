"""Free-caption-only transcript extraction for the agent API.

Deliberate scope limit, by design:
- Tier 1: youtube-transcript-api (free)
- Tier 2: yt-dlp caption tracks (free)
- There is NO third tier in this module. No paid transcription code
  exists here at all, so a no-caption video can never silently spend
  money. It returns NoCaptionsError instead.

No database, no auth, no account. One call in, structured JSON out.
"""

import os
import re
from urllib.parse import urlparse, parse_qs

import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

CAPTION_TIMEOUT = 60  # sandbox egress proxy is slow; 12s timed out on YouTube


class NoCaptionsError(RuntimeError):
    pass


def is_youtube_url(url: str) -> bool:
    u = url.lower()
    return "youtube.com" in u or "youtu.be" in u


def extract_video_id(url: str):
    try:
        if "youtu.be" in url:
            return url.split("/")[-1].split("?")[0].split("&")[0]
        parsed = urlparse(url)
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        for prefix in ("/embed/", "/v/", "/shorts/"):
            if parsed.path.startswith(prefix):
                return parsed.path.split("/")[2]
    except Exception:
        pass
    return None


def _lang_list(lang: str):
    if lang == "zh":
        return ["zh-CN", "zh-Hans", "zh-Hant", "zh-TW", "zh"]
    if lang == "en":
        return ["en"]
    return ["zh-CN", "zh-Hans", "zh", "en"]  # auto


def _fetch_captions_api(video_id: str, lang: str):
    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=_lang_list(lang))
    segments, parts = [], []
    for s in fetched.snippets:
        text = s.text.strip()
        if not text:
            continue
        parts.append(text)
        start = float(s.start or 0)
        segments.append(
            {"start": round(start, 2),
             "end": round(start + float(s.duration or 0), 2),
             "text": text}
        )
    text = " ".join(parts).strip()
    if not text:
        raise RuntimeError("empty transcript from caption API")
    return text, segments


def _parse_vtt_segments(raw: str):
    ts_re = re.compile(
        r"(\d{1,3}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,3}:\d{2}:\d{2}[.,]\d{3})"
    )

    def to_sec(ts: str) -> float:
        h, m, s = ts.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    segments, cur = [], None
    for ln in raw.splitlines():
        line = ln.strip()
        m = ts_re.search(line)
        if m:
            if cur and cur["t"]:
                segments.append(cur)
            cur = {"start": round(to_sec(m.group(1)), 2),
                   "end": round(to_sec(m.group(2)), 2), "text": ""}
        elif not line:
            if cur and cur["t"]:
                segments.append(cur)
                cur = None
        elif cur is not None:
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean and not re.match(r"^\d+$", clean) and clean != "WEBVTT":
                cur["text"] = (cur["text"] + " " + clean).strip()
    if cur and cur["t"]:
        segments.append(cur)
    out, prev = [], None
    for sg in segments:
        if sg["text"] != prev:
            out.append(sg)
        prev = sg["text"]
    return out


def _fetch_captions_ytdlp(url: str, lang: str):
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": CAPTION_TIMEOUT,
    }
    cookie_file = os.getenv("YTDLP_COOKIE_FILE", "cookies.txt")
    if os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    # Sandbox-only: the sandbox egress proxy MITMs TLS and yt-dlp's
    # `cacert` option does not take effect through its proxy CONNECT
    # (verified 2026-11-06: cacert set, still CERTIFICATE_VERIFY_FAILED;
    # requests/curl verify fine with the same CA). Set YTDLP_NOVERIFY=1
    # ONLY for local sandbox testing. Never set it on Vultr/production,
    # where there is no MITM proxy and verification stays on.
    if os.getenv("YTDLP_NOVERIFY") == "1":
        ydl_opts["nocheckcertificate"] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    subs_all = info.get("subtitles") or {}
    auto_all = info.get("automatic_captions") or {}

    def pick_track(all_tracks: dict):
        keys = _lang_list(lang)
        for k in keys:
            if all_tracks.get(k):
                return all_tracks[k]
        for k, v in all_tracks.items():
            if v:
                return v
        return []

    subs = pick_track(subs_all) or pick_track(auto_all)
    json3_url = next((s.get("url") for s in subs if s.get("ext") == "json3"), None)
    if not json3_url:
        vtt_url = next((s.get("url") for s in subs if s.get("url")), None)
        if not vtt_url:
            raise RuntimeError("no caption tracks found")
        raw = requests.get(vtt_url, timeout=CAPTION_TIMEOUT).text
        segments = _parse_vtt_segments(raw)
        text = " ".join(sg["text"] for sg in segments).strip()
        if not text:
            raise RuntimeError("caption track parsed empty")
        return text, segments
    data = requests.get(json3_url, timeout=CAPTION_TIMEOUT).json()
    segments, parts = [], []
    for event in data.get("events", []):
        t = "".join(seg.get("utf8", "") for seg in event.get("segs", [])).strip()
        if not t:
            continue
        parts.append(t)
        s = (event.get("tStartMs") or 0) / 1000
        d = (event.get("dDurationMs") or 0) / 1000
        segments.append({"start": round(s, 2), "end": round(s + d, 2), "text": t})
    text = " ".join(parts).replace("\n", " ").strip()
    if not text:
        raise RuntimeError("caption track parsed empty")
    return text, segments


def get_transcript_free(url: str, lang: str = "auto") -> dict:
    """Return transcript dict, or raise NoCaptionsError. Never spends money."""
    if not is_youtube_url(url):
        raise ValueError("only YouTube URLs are supported in this free tier")
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("could not parse a video id from this URL")
    errors = []
    try:
        text, segments = _fetch_captions_api(video_id, lang)
        return {"video_id": video_id, "transcript": text,
                "segments": segments, "source": "captions_api",
                "cost_usd": 0}
    except Exception as e:
        errors.append(f"captions_api: {e}")
    try:
        text, segments = _fetch_captions_ytdlp(url, lang)
        return {"video_id": video_id, "transcript": text,
                "segments": segments, "source": "ytdlp",
                "cost_usd": 0}
    except Exception as e:
        errors.append(f"ytdlp: {e}")
    raise NoCaptionsError("no_captions; free tiers failed: " + " | ".join(errors))
