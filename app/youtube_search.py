"""Free YouTube search for agents, $0, no API key, no paid service.

Uses yt-dlp's ytsearch (public YouTube search results, no YouTube Data API
key, no paid tier). Returns structured JSON only. This is a separate
codebase from both the live agent-transcript API and the human-facing
Transcriptly app; nothing here touches either.
"""
import json
import os
import re

import requests
import yt_dlp

SEARCH_TIMEOUT = 60
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def _dur_to_sec(s):
    try:
        parts = [int(p) for p in s.strip().split(":")]
        out = 0
        for p in parts:
            out = out * 60 + p
        return out
    except Exception:
        return None


def _search_html(query: str, n: int):
    """Fallback: parse public YouTube search page (ytInitialData).

    Used only when yt-dlp's search path fails (in this sandbox it fails on
    the egress proxy's MITM CA, which yt-dlp's client does not honour).
    Same public data yt-dlp reads; no login, no API key.
    """
    r = requests.get("https://www.youtube.com/results",
                     params={"search_query": query}, headers=UA, timeout=SEARCH_TIMEOUT)
    r.raise_for_status()
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
    if not m:
        raise RuntimeError("ytInitialData not found in search page")
    data = json.loads(m.group(1))
    results = []

    def walk(node):
        if isinstance(node, dict):
            vr = node.get("videoRenderer")
            if vr and vr.get("videoId"):
                title = "".join(t.get("text", "") for t in vr.get("title", {}).get("runs", []))
                results.append({
                    "video_id": vr["videoId"],
                    "title": title or None,
                    "url": f"https://www.youtube.com/watch?v={vr['videoId']}",
                    "channel": "".join(t.get("text", "") for t in vr.get("longBylineText", {}).get("runs", [])) or None,
                    "duration_seconds": _dur_to_sec(vr.get("lengthText", {}).get("simpleText", "")),
                    "view_count": vr.get("viewCountText", {}).get("simpleText"),
                })
                if len(results) >= n:
                    return
            for v in node.values():
                if len(results) >= n:
                    return
                walk(v)
        elif isinstance(node, list):
            for v in node:
                if len(results) >= n:
                    return
                walk(v)

    walk(data)
    if not results:
        raise RuntimeError("no videoRenderer entries in search page")
    return results


def search_youtube(query: str, max_results: int = 5) -> dict:
    q = (query or "").strip()
    if not q:
        raise ValueError("query is required")
    n = max(1, min(int(max_results), 10))
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": SEARCH_TIMEOUT,
        "extract_flat": True,
    }
    # Test-only override (sandbox egress proxy MITMs TLS). Production on
    # Fly uses the normal system CA bundle and must NOT set this.
    cacert = os.getenv("YTDLP_CACERT")
    if cacert:
        ydl_opts["cacert"] = cacert
    errors = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{q}", download=False)
        entries = info.get("entries") or []
        results = []
        for e in entries:
            if not e:
                continue
            vid = e.get("id")
            results.append({
                "video_id": vid,
                "title": e.get("title"),
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else e.get("url"),
                "channel": e.get("channel") or e.get("uploader"),
                "duration_seconds": e.get("duration"),
                "view_count": e.get("view_count"),
            })
        if results:
            return {"query": q, "results": results, "count": len(results),
                    "source": "ytdlp_search", "cost_usd": 0}
        errors.append("ytdlp: empty")
    except Exception as e:
        errors.append(f"ytdlp: {e}"[:200])
    results = _search_html(q, n)
    return {"query": q, "results": results, "count": len(results),
            "source": "html_search_fallback", "cost_usd": 0,
            "note": "ytdlp search failed in sandbox; " + " | ".join(errors)[:200]}
