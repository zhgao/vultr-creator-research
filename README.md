# vultr-creator-research

Creator-research workflow for the **Vultr Agent Rush, Challenge 2 — Powering the Future of Work**.

## What it does

Enter a research topic and the service runs a real multi-step workflow:

1. **Topic → YouTube search** — searches YouTube for the topic (yt-dlp search, no API key).
2. **Free captions** — fetches free captions for the top videos (youtube-transcript-api, then yt-dlp caption tracks).
3. **Brief** — builds a structured brief with key segments, `[MM:SS]` timestamps, source video links, and a draft outreach note.

No mock data: search and captions are real calls. The `/research` page shows the steps (searching → fetching captions → building brief) and the result table with a one-click copy of the brief and outreach draft.

## Demo

- Fly demo: <FLY DEMO URL — fill after deployment>
- Vultr demo: <VULTR DEMO URL — fill after VM deploy>

## How this runs on Vultr (Agent Rush, Challenge 2)

- **Vultr VM — backend and control layer.** The FastAPI service runs in Docker
  on a Vultr Cloud Compute instance. It is the central orchestrator: it takes
  a research topic, plans the steps (search → transcript → brief), calls each
  step in order, and returns one structured brief. It is not static hosting.
- **What the agent does, in real steps.** (1) Search YouTube for the topic
  (existing yt-dlp search, no API key). (2) Fetch free captions for the top
  videos (youtube-transcript-api, then yt-dlp caption tracks). Videos without
  captions are skipped and reported as skipped — never invented.
  (3) Build a brief: key segments with `[MM:SS]` timestamps, source video links,
  and a draft outreach note. The deterministic version of step (3) needs no LLM;
  an optional Vultr Serverless Inference summarizer can be enabled with an
  environment flag and falls back to the deterministic brief when unset.
- **What is NOT on Vultr in this demo.** No paid x402 endpoints, no wallet
  address, no secrets in the repo or in the demo. The live Fly deployment of
  agent-transcript is a separate deployment and is untouched by this build.
- **Public demo.** <VULTR DEMO URL — fill in after deployment>

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
uvicorn app.main:app --port 8080
```

Open http://localhost:8080/research

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/agent/v1/youtube-search` | Search YouTube for a topic |
| GET | `/agent/v1/transcript` | Fetch free captions for a video |
| POST | `/workflow/creator-research` | Start a creator-research workflow (`{topic, max_videos}`) |
| GET | `/workflow/creator-research/{job_id}` | Workflow status and result |
| GET | `/research` | Product page: topic input, step progress, brief results |

## Deploy

- **Fly.io:** `fly.toml` is in the repo root; GitHub Actions (`.github/workflows/deploy.yml`) deploys on push to `main` with the `FLY_API_TOKEN` secret. Region `sin`, 1 shared CPU / 512 MB.
- **Vultr VM:** see [deploy/VULTR_VM_README.md](deploy/VULTR_VM_README.md) and run `deploy/vultr-vm-deploy.sh` on the VM.

## Honesty notes

- No LLM is used in the deterministic brief; the optional Vultr Serverless Inference summarizer is off unless explicitly enabled.
- No paid endpoints: the demo uses only the free search and free caption paths. No wallet, no x402.
- Videos without captions are skipped and reported as skipped — never invented or faked as transcribed.

## License

MIT

## Cost

$0 — free tiers and existing resources only; no paid services, no new accounts.
