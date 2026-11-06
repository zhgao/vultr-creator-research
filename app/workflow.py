"""Creator-research workflow for the Vultr Agent Rush Challenge 2 build.

$0, free captions only. Free endpoints only; nothing here charges
or reads any address or credential.
A video with no captions is recorded as skipped — transcript content
is never invented.
"""

import re
from datetime import datetime, timezone

from .free_transcript import NoCaptionsError, get_transcript_free
from .youtube_search import search_youtube

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "it", "its", "this", "that", "you", "your",
    "we", "they", "he", "she", "i", "me", "my", "as", "at", "by", "from",
    "not", "but", "so", "if", "do", "does", "did", "can", "will", "just",
    "like", "about", "how", "what", "when", "why", "get", "got", "have",
    "has", "had", "be", "been", "there", "here", "all", "more", "best",
    "review", "video",
}


def _keywords(topic: str) -> set:
    words = re.findall(r"[a-z0-9]+", topic.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _mmss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _pick_segments(topic: str, segments: list, video_url: str, top_n: int = 3):
    """Deterministic brief: score segments by topic-keyword overlap + length."""
    keys = _keywords(topic)
    scored = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        low = text.lower()
        overlap = sum(1 for k in keys if k in low)
        # keyword hits dominate; length breaks ties (longer = more substance),
        # capped so a rambling segment cannot win on length alone.
        score = overlap * 100 + min(len(text), 200)
        scored.append((score, seg, text))
    scored.sort(key=lambda t: (-t[0], t[1].get("start", 0)))
    out = []
    for _score, seg, text in scored[:top_n]:
        secs = int(float(seg.get("start", 0)))
        out.append({
            "timestamp": f"[{_mmss(secs)}]",
            "seconds": secs,
            "text": text[:200],
            "url": f"{video_url}&t={secs}s",
        })
    return out


def _outreach_draft(topic: str, videos: list) -> str:
    """Built ONLY from real segment text + real video titles/channels."""
    lines = [
        f"Hi — I'm researching '{topic}' and your video stood out.",
        "",
    ]
    for v in videos:
        segs = v.get("segments") or []
        title = v.get("title") or "your video"
        channel = v.get("channel") or "you"
        if segs:
            s = segs[0]
            lines.append(
                f"Hi {channel}, your video '{title}' at {s['timestamp']} says "
                f"'{s['text']}' — that's exactly the angle I'm covering. "
                f"Would you be open to a short chat? Link: {s['url']}"
            )
        else:
            lines.append(
                f"Hi {channel}, your video '{title}' looks like a great fit "
                f"for my '{topic}' research — would you be open to a short chat?"
            )
        lines.append("")
    lines.append(
        "Template only — edit before sending. Every quote above comes "
        "from the video's own captions."
    )
    return "\n".join(lines).strip()


def run_workflow(topic: str, max_videos: int, job: dict) -> None:
    """Runs in a background thread; mutates job in place.

    job shape: {"job_id","status","topic","steps":[...],"result","error"}
    Steps: search -> transcripts -> brief.
    """
    steps = job["steps"]

    def set_step(name, status, detail="", done=0, total=0):
        for s in steps:
            if s["name"] == name:
                s["status"] = status
                s["detail"] = detail
                s["done"] = done
                s["total"] = total

    try:
        set_step("search", "running", f"Searching YouTube for '{topic}'…")
        found = search_youtube(topic, max_videos)
        videos_meta = found.get("results") or []
        set_step("search", "done",
                 f"Found {len(videos_meta)} video(s).", len(videos_meta),
                 len(videos_meta))
        if not videos_meta:
            job["status"] = "done"
            job["result"] = {
                "topic": topic,
                "videos": [],
                "skipped": [],
                "outreach_draft": "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            set_step("transcripts", "done", "No videos to transcribe.", 0, 0)
            set_step("brief", "done", "Nothing to brief.", 0, 0)
            return

        set_step("transcripts", "running", "Fetching captions…",
                 0, len(videos_meta))
        videos, skipped = [], []
        for i, meta in enumerate(videos_meta):
            url = meta.get("url") or ""
            vid = meta.get("video_id") or ""
            try:
                tr = get_transcript_free(url)
                segments = _pick_segments(topic, tr.get("segments") or [], url)
                videos.append({
                    "video_id": vid,
                    "title": meta.get("title"),
                    "channel": meta.get("channel"),
                    "url": url,
                    "duration_seconds": meta.get("duration_seconds"),
                    "segments": segments,
                    "segment_count": len(tr.get("segments") or []),
                    "source": tr.get("source"),
                })
                set_step("transcripts", "running",
                         f"Transcribed {len(videos)}/{len(videos_meta)} "
                         f"({len(skipped)} skipped).",
                         i + 1, len(videos_meta))
            except NoCaptionsError:
                skipped.append({
                    "video_id": vid,
                    "title": meta.get("title"),
                    "url": url,
                    "reason": "no_captions",
                })
                set_step("transcripts", "running",
                         f"Transcribed {len(videos)}/{len(videos_meta)} "
                         f"({len(skipped)} skipped — no captions).",
                         i + 1, len(videos_meta))
            except Exception as e:  # search/transcript infra error, not fatal
                skipped.append({
                    "video_id": vid,
                    "title": meta.get("title"),
                    "url": url,
                    "reason": f"error: {str(e)[:120]}",
                })
                set_step("transcripts", "running",
                         f"Transcribed {len(videos)}/{len(videos_meta)} "
                         f"({len(skipped)} skipped).",
                         i + 1, len(videos_meta))
        set_step("transcripts", "done",
                 f"{len(videos)} transcribed, {len(skipped)} skipped.",
                 len(videos_meta), len(videos_meta))

        set_step("brief", "running", "Picking top segments and drafting outreach…")
        draft = _outreach_draft(topic, videos)
        set_step("brief", "done", "Brief ready.", 1, 1)

        job["result"] = {
            "topic": topic,
            "videos": videos,
            "skipped": skipped,
            "outreach_draft": draft,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)[:500]
        for s in steps:
            if s["status"] in ("running", "pending"):
                s["status"] = "error"
                s["detail"] = str(e)[:200]
