# creator-research — local self-test evidence

Date: 2026-11-06 (Beijing, ~23:50–2026-11-07 00:05). Tester: Muse (subagent).
Rule followed: test first, show evidence. No pip installs; used the
existing venv read-only: `~/workspace/agent-sales-exploration/.venv/bin/python`.

## How the server was run

```bash
cd ~/workspace/vultr-creator-research
SSL_CERT_FILE=/usr/local/share/ca-certificates/hatch-egress-ca.crt \
YTDLP_CACERT=/usr/local/share/ca-certificates/hatch-egress-ca.crt \
YTDLP_NOVERIFY=1 \
~/workspace/agent-sales-exploration/.venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 8090
```

`YTDLP_NOVERIFY=1` is sandbox-only (see "Sandbox findings" below). It was
NOT baked into any file; it is an env flag, off by default. Production on
Vultr must not set it.

## Endpoint status codes

| Check | Result |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `GET /research` | 200 |
| `GET /research?topic=sourdough%20bread%20baking%20tutorial&autorun=1` | 200 |
| `GET /docs` | 200 (FastAPI default docs enabled) |
| `GET /openapi.json` | 200 |
| `GET /agent/v1/youtube-search?q=sourdough%20bread%20baking%20tutorial&max_results=3` | 200, `count: 3`, `source: html_search_fallback` |
| `GET /agent/v1/youtube-search?q=mechanical%20keyboard%20review&max_results=3` (first call) | 502 `search_failed` — yt-dlp SSL failed AND the HTML fallback page had no `ytInitialData` that once; later identical searches returned 200 (see below) |
| `GET /agent/v1/transcript?url=https://example.com/x` | 400 `{"error":"not_youtube",...}` |
| `GET /agent/v1/transcript?url=https://www.youtube.com/watch?v=4gEoh3sk2AE` | 404 `{"error":"no_captions",...}` — same video succeeded minutes earlier via the workflow; the 404 is YouTube's flaky bot-check on a repeatedly-hit video ID (see "Sandbox findings"), NOT a missing-captions video. Error shape is as specified. |
| `POST /workflow/creator-research` with `{"topic":""}` | 400 `topic_required` |
| `POST /workflow/creator-research` with `{"topic":"test clamp","max_videos":99}` | 202, and the job's search step ran `5/5` — clamp 1..5 verified |
| `GET /workflow/creator-research/nope123` | 404 `job_not_found` |

## Workflow run 1 — "mechanical keyboard review" (job `039056cbd6bc`)

- POST 202, polled to `done` in ~20 s (this run was BEFORE the sandbox
  `YTDLP_NOVERIFY` flag, so yt-dlp failed TLS in this sandbox).
- Search: 3/3 found. Transcripts: **0 transcribed, 3 skipped** (`no_captions`).
- Videos found (search worked via the HTML fallback):
  - `8ta4dSQ-P9c` "The Best Keyboard at Every Price (Don't Waste your Money)"
  - `BWQFUPm6XE0` "Beginner's Guide To Mechanical Keyboards"
  - `3rKPzh3Pr0o` "Full-Sized Keyboards are FINALLY Good in 2026."
- Outreach draft contained no quotes (no transcribed video) — correctly
  empty of invented content, only the header + template footer.

## Workflow run 2 (the real one) — "sourdough bread baking tutorial" (job `a4ff81fb97ad`)

- POST 202, polled every 10 s, `done` in **21 s** total (POST → done).
- Step progression observed live: `search:done 3/3` →
  `transcripts:running 0/3 → 3/3` → `brief:done 1/1`.
- **1 video transcribed, 2 skipped.**

### Transcribed

- `4gEoh3sk2AE` — "Bake the Perfect Sourdough Bread: A Step-by-Step Guide",
  channel Natashas Kitchen, 713 s, source `ytdlp`, **319 caption segments**.
  Top 3 picked segments (deterministic keyword-overlap + length scoring):
  - `[00:08]` "And I'm craving some sourdough bread, so let's get started."
    → https://www.youtube.com/watch?v=4gEoh3sk2AE&t=8s
  - `[00:00]` "- Today I am gonna show you how to make sourdough bread."
    → https://www.youtube.com/watch?v=4gEoh3sk2AE&t=0s
  - `[06:45]` "to make a beautiful loaf of your own sourdough bread."
    → https://www.youtube.com/watch?v=4gEoh3sk2AE&t=405s

### Skipped (honest, no content invented)

- `s8dQ2hnYqp0` — "STEP-BY-STEP SOURDOUGH FOR BEGINNERS: How to Make Sourdough Starter & Sourdough Bread" — `no_captions`
- `CTuGXdyrWUo` — "The BEST Beginner Sourdough Bread Tutorial on YouTube" — `no_captions`

### Outreach draft (verbatim, built only from the real quote above)

> Hi — I'm researching 'sourdough bread baking tutorial' and your video stood out.
>
> Hi Natashas Kitchen, your video 'Bake the Perfect Sourdough Bread: A Step-by-Step Guide' at [00:08] says 'And I'm craving some sourdough bread, so let's get started.' — that's exactly the angle I'm covering. Would you be open to a short chat? Link: https://www.youtube.com/watch?v=4gEoh3sk2AE&t=8s
>
> Template only — edit before sending. Every quote above comes from the video's own captions.

### Full brief JSON (job `a4ff81fb97ad`, `generated_at` 2026-11-06T16:00:35Z)

```json
{
 "topic": "sourdough bread baking tutorial",
 "videos": [
  {
   "video_id": "4gEoh3sk2AE",
   "title": "Bake the Perfect Sourdough Bread: A Step-by-Step Guide",
   "channel": "Natashas Kitchen",
   "url": "https://www.youtube.com/watch?v=4gEoh3sk2AE",
   "duration_seconds": 713,
   "segments": [
    {"timestamp": "[00:08]", "seconds": 8,
     "text": "And I'm craving some sourdough\nbread, so let's get started.",
     "url": "https://www.youtube.com/watch?v=4gEoh3sk2AE&t=8s"},
    {"timestamp": "[00:00]", "seconds": 0,
     "text": "- Today I am gonna show you\nhow to make sourdough bread.",
     "url": "https://www.youtube.com/watch?v=4gEoh3sk2AE&t=0s"},
    {"timestamp": "[06:45]", "seconds": 405,
     "text": "to make a beautiful loaf of\nyour own sourdough bread.",
     "url": "https://www.youtube.com/watch?v=4gEoh3sk2AE&t=405s"}
   ],
   "segment_count": 319,
   "source": "ytdlp"
  }
 ],
 "skipped": [
  {"video_id": "s8dQ2hnYqp0",
   "title": "STEP-BY-STEP SOURDOUGH FOR BEGINNERS: How to Make Sourdough Starter & Sourdough Bread",
   "url": "https://www.youtube.com/watch?v=s8dQ2hnYqp0", "reason": "no_captions"},
  {"video_id": "CTuGXdyrWUo",
   "title": "The BEST Beginner Sourdough Bread Tutorial on YouTube",
   "url": "https://www.youtube.com/watch?v=CTuGXdyrWUo", "reason": "no_captions"}
 ],
 "outreach_draft": "Hi — I'm researching 'sourdough bread baking tutorial' and your video stood out.\n\nHi Natashas Kitchen, your video 'Bake the Perfect Sourdough Bread: A Step-by-Step Guide' at [00:08] says 'And I'm craving some sourdough\nbread, so let's get started.' — that's exactly the angle I'm covering. Would you be open to a short chat? Link: https://www.youtube.com/watch?v=4gEoh3sk2AE&t=8s\n\nTemplate only — edit before sending. Every quote above comes from the video's own captions.",
 "generated_at": "2026-11-06T16:00:35.620714+00:00"
}
```

## Curl commands used (reproducible against the local server)

```bash
curl -s http://127.0.0.1:8090/health
curl -s "http://127.0.0.1:8090/agent/v1/youtube-search?q=sourdough%20bread%20baking%20tutorial&max_results=3"
curl -s "http://127.0.0.1:8090/agent/v1/transcript?url=https://www.youtube.com/watch?v=4gEoh3sk2AE&lang=en"
curl -s -X POST http://127.0.0.1:8090/workflow/creator-research \
  -H 'Content-Type: application/json' \
  -d '{"topic":"sourdough bread baking tutorial","max_videos":3}'
curl -s http://127.0.0.1:8090/workflow/creator-research/a4ff81fb97ad
curl -s http://127.0.0.1:8090/research
```

## Sandbox findings (why the first run failed, and the one code change made)

1. **yt-dlp TLS vs the egress proxy.** The sandbox proxy MITMs TLS. `curl`
   and `requests` verify fine with `SSL_CERT_FILE=<Hatch CA>`, but yt-dlp
   still fails `CERTIFICATE_VERIFY_FAILED` even with its `cacert` option
   pointed at the same CA (tested with both the `.crt` path and the real
   `.pem` target). Search still worked because the copied
   `youtube_search.py` falls back to parsing the search HTML via `requests`.
   Transcripts had no such fallback.
2. **Fix (copy only, source untouched):** in the new dir's copy of
   `app/free_transcript.py`, `_fetch_captions_ytdlp` now passes
   `nocheckcertificate=True` ONLY when env `YTDLP_NOVERIFY=1`. Default is
   off, so on Vultr (no MITM proxy) TLS verification stays on. This flag
   is a local-sandbox-testing workaround, documented in a comment at the
   change site.
3. **YouTube bot-check flakiness from the sandbox egress IP.** After a
   burst of requests to the same video IDs, YouTube returns "Sign in to
   confirm you're not a bot" (yt-dlp) and an IP-block message
   (youtube-transcript-api); the direct `timedtext` endpoint returns 200
   with an empty body, and innertube `player` returns `LOGIN_REQUIRED`
   with zero caption tracks. Fresh video IDs work (the sourdough run
   proves it); repeatedly-hit IDs fail. This is a sandbox-IP limitation,
   not an app bug — the app records these honestly as `no_captions` skips
   and never invents transcript text. On the Vultr VM (its own IP, no
   burst) this should behave better; if the demo hits it live, use a
   fresh topic.
4. **First search 502 was transient.** The very first search call failed
   both paths (yt-dlp SSL + HTML page without `ytInitialData`); identical
   later searches returned 200 via the HTML fallback.

## What was NOT tested

- Real deployment on Vultr (out of scope for this local test; `deploy/`
  and `fly.toml` in the new dir were pre-existing from the parent and were
  not touched).
- The `/research` page's JS polling end-to-end in a real browser (page
  HTML verified served 200 and contains the 1 s `setTimeout` poll loop,
  `?topic=`/`autorun=1` handling, and the clipboard-with-textarea-fallback
  copy button by source inspection only). The same polling logic was
  exercised via curl against the job endpoint.
- No spend: $0. No new accounts created. Nothing outside
  `~/workspace/vultr-creator-research/` was modified; the live
  agent-transcript Fly deployment and ClipPay were not touched.
