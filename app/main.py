"""creator-research — Vultr Agent Rush Challenge 2 minimum app.

Free YouTube search + free-caption transcripts + a deterministic
creator-research workflow (search -> transcripts -> brief).

$0 build. Free endpoints only; nothing in this file reads any
address or credential from the environment.
FastAPI default docs stay enabled (/docs, /openapi.json).
"""

import threading
import uuid

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .free_transcript import (
    NoCaptionsError,
    get_transcript_free,
    is_youtube_url,
)
from .workflow import run_workflow
from .youtube_search import search_youtube

app = FastAPI(title="creator-research", version="0.1.0")

# In-memory job store: {job_id: job dict}
JOBS: dict = {}


def _new_job(topic: str, max_videos: int) -> dict:
    return {
        "job_id": uuid.uuid4().hex[:12],
        "status": "running",
        "topic": topic,
        "max_videos": max_videos,
        "steps": [
            {"name": "search", "status": "pending", "detail": "",
             "done": 0, "total": 0},
            {"name": "transcripts", "status": "pending", "detail": "",
             "done": 0, "total": 0},
            {"name": "brief", "status": "pending", "detail": "",
             "done": 0, "total": 0},
        ],
        "result": None,
        "error": None,
    }


def _public_job(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "topic": job["topic"],
        "steps": job["steps"],
        "result": job["result"],
        "error": job["error"],
    }


# ---------------------------------------------------------------- health
@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------- free agent tools
@app.get("/agent/v1/youtube-search")
def youtube_search(q: str = Query(""), max_results: int = Query(5)):
    try:
        return search_youtube(q, max_results)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=502,
                            content={"error": "search_failed",
                                     "detail": str(e)[:200]})


@app.get("/agent/v1/transcript")
def transcript(url: str = Query(...), lang: str = Query("auto")):
    if not is_youtube_url(url):
        return JSONResponse(
            status_code=400,
            content={"error": "not_youtube",
                     "detail": "only YouTube URLs are supported in this free tier"},
        )
    try:
        return get_transcript_free(url, lang=lang)
    except NoCaptionsError as e:
        return JSONResponse(
            status_code=404,
            content={"error": "no_captions",
                     "detail": str(e),
                     "paid_fallback": False,
                     "paid_fallback_attempted": False},
        )
    except ValueError as e:
        return JSONResponse(status_code=400,
                            content={"error": "bad_url", "detail": str(e)})


# ------------------------------------------------------------- workflow
class CreatorResearchRequest(BaseModel):
    topic: str
    max_videos: int = 3


@app.post("/workflow/creator-research", status_code=202)
def start_creator_research(body: CreatorResearchRequest):
    topic = (body.topic or "").strip()
    if not topic:
        return JSONResponse(status_code=400,
                            content={"error": "topic_required",
                                     "detail": "topic is required"})
    if len(topic) > 200:
        return JSONResponse(status_code=400,
                            content={"error": "topic_too_long",
                                     "detail": "topic must be at most 200 characters"})
    max_videos = max(1, min(int(body.max_videos or 3), 5))
    job = _new_job(topic, max_videos)
    JOBS[job["job_id"]] = job
    thread = threading.Thread(
        target=run_workflow, args=(topic, max_videos, job), daemon=True)
    thread.start()
    step_names = [s["name"] for s in job["steps"]]
    return JSONResponse(
        status_code=202,
        content={"job_id": job["job_id"], "status": "running",
                 "steps": step_names},
    )


@app.get("/workflow/creator-research/{job_id}")
def get_creator_research(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse(status_code=404,
                            content={"error": "job_not_found",
                                     "detail": f"no job {job_id}"})
    return _public_job(job)


# ---------------------------------------------------------------- pages
LANDING_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>creator-research</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
margin:0;color:#1d1d1f;background:#fff}
main{max-width:680px;margin:0 auto;padding:96px 24px;text-align:center}
h1{font-size:48px;font-weight:700;letter-spacing:-0.02em;margin:0 0 16px}
p{font-size:19px;line-height:1.6;color:#6e6e73;margin:0 0 32px}
a.btn{display:inline-block;background:#0071e3;color:#fff;text-decoration:none;
font-size:17px;padding:14px 32px;border-radius:980px}
a.btn:hover{background:#0077ed}
small{display:block;margin-top:48px;color:#86868b;font-size:13px}
code{color:#6e6e73}
</style></head><body><main>
<h1>creator-research</h1>
<p>Pick a topic. We search YouTube, read the free captions, and hand you
a brief: the moments worth quoting, with timestamps and source links —
plus a short outreach draft built only from what creators actually said.</p>
<a class="btn" href="/research">Start researching →</a>
<small>Free captions only · $0 · Videos without captions are skipped, never invented.<br>
API: <code>GET /agent/v1/youtube-search</code> · <code>GET /agent/v1/transcript</code> ·
<code>POST /workflow/creator-research</code> · Docs: <a href="/docs">/docs</a></small>
</main></body></html>"""


@app.get("/", response_class=HTMLResponse)
def landing():
    return LANDING_HTML


RESEARCH_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Creator research — creator-research</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
margin:0;color:#1d1d1f;background:#fff}
main{max-width:720px;margin:0 auto;padding:64px 24px 96px}
h1{font-size:40px;font-weight:700;letter-spacing:-0.02em;margin:0 0 8px}
.sub{font-size:17px;line-height:1.6;color:#6e6e73;margin:0 0 32px}
form{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}
input[type=text]{flex:1;min-width:240px;font-size:17px;padding:14px 20px;
border:1px solid #d2d2d7;border-radius:980px;outline:none}
input[type=text]:focus{border-color:#0071e3}
button{font-size:17px;background:#0071e3;color:#fff;border:0;padding:14px 28px;
border-radius:980px;cursor:pointer}
button:disabled{background:#a0c8f0;cursor:default}
button.ghost{background:#f5f5f7;color:#0071e3}
.hint{font-size:13px;color:#86868b;margin:0 0 32px}
.step{display:flex;gap:12px;align-items:baseline;padding:14px 0;
border-top:1px solid #f5f5f7}
.step .dot{width:10px;height:10px;border-radius:50%;background:#d2d2d7;flex:none;
transform:translateY(-1px)}
.step.running .dot{background:#0071e3}
.step.done .dot{background:#34c759}
.step.error .dot{background:#ff3b30}
.step .name{font-weight:600;width:110px;flex:none}
.step .detail{color:#6e6e73;font-size:15px}
.video{margin:32px 0 8px}
.video h3{font-size:20px;margin:0 0 4px}
.video h3 a{color:#1d1d1f;text-decoration:none}
.video h3 a:hover{color:#0071e3}
.video .meta{font-size:14px;color:#86868b;margin:0 0 12px}
.seg{border-left:3px solid #0071e3;padding:4px 0 4px 14px;margin:0 0 14px}
.seg .ts{font-weight:600}
.seg .ts a{color:#0071e3;text-decoration:none}
.seg p{margin:4px 0 0;font-size:16px;line-height:1.55}
.skipped{color:#86868b;font-size:14px;margin:8px 0}
pre{background:#f5f5f7;border-radius:12px;padding:20px;white-space:pre-wrap;
word-wrap:break-word;font-size:14px;line-height:1.6;overflow-x:auto}
.err{color:#ff3b30}
.note{font-size:13px;color:#86868b;margin-top:48px;line-height:1.6}
h2{font-size:24px;margin:40px 0 8px}
</style></head><body><main>
<h1>Creator research</h1>
<p class="sub">Enter a topic. We search YouTube, read the free captions, and
build a brief of quotable moments — with timestamps and source links.</p>
<form id="f">
<input type="text" id="topic" placeholder="e.g. mechanical keyboard review"
 maxlength="200" autocomplete="off">
<button type="submit" id="go">Start</button>
</form>
<p class="hint">Up to 5 videos per run. Videos without captions are skipped — never invented.</p>
<div id="steps"></div>
<div id="results"></div>
<p class="note">How it works: search → captions → brief. Everything here comes
from public YouTube search results and free caption tracks. No account,
no account, no charge. A video with no captions is listed
under “skipped” and contributes nothing to the brief.</p>
</main>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let timer = null;

function renderSteps(job){
  $("steps").innerHTML = job.steps.map(s =>
    `<div class="step ${esc(s.status)}"><span class="dot"></span>
     <span class="name">${esc(s.name)}</span>
     <span class="detail">${esc(s.detail || s.status)}${s.total ? ` (${s.done}/${s.total})` : ""}</span>
     </div>`).join("");
}
function renderResults(job){
  const r = job.result;
  if(!r) return;
  let html = `<h2>Brief — ${esc(r.topic)}</h2>
    <p class="hint">Generated ${esc(r.generated_at || "")}</p>`;
  if(r.videos.length === 0) html += `<p>No videos with captions found for this topic.</p>`;
  for(const v of r.videos){
    html += `<div class="video"><h3><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title || v.video_id)}</a></h3>
      <p class="meta">${esc(v.channel || "")}${v.duration_seconds ? " · " + Math.round(v.duration_seconds/60) + " min" : ""} · ${v.segment_count} caption segments</p>`;
    for(const s of v.segments){
      html += `<div class="seg"><span class="ts"><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.timestamp)}</a></span>
        <p>${esc(s.text)}</p></div>`;
    }
    html += `</div>`;
  }
  if(r.skipped.length){
    html += `<h2>Skipped</h2>`;
    for(const s of r.skipped){
      html += `<p class="skipped">— <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.video_id)}</a> (${esc(s.reason)})</p>`;
    }
  }
  if(r.outreach_draft){
    html += `<h2>Outreach draft</h2>
      <button class="ghost" id="copy">Copy brief</button>
      <pre id="draft">${esc(r.outreach_draft)}</pre>`;
  }
  $("results").innerHTML = html;
  const copy = $("copy");
  if(copy) copy.onclick = async () => {
    const text = $("draft").innerText;
    try { await navigator.clipboard.writeText(text); copy.textContent = "Copied ✓"; }
    catch(e){
      const ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); copy.textContent = "Copied ✓"; }
      catch(e2){ copy.textContent = "Copy failed — select the text manually"; }
      ta.remove();
    }
    setTimeout(() => { copy.textContent = "Copy brief"; }, 2000);
  };
}
async function poll(jobId){
  const res = await fetch("/workflow/creator-research/" + jobId);
  const job = await res.json();
  renderSteps(job);
  if(job.status === "done"){ renderResults(job); $("go").disabled = false; $("go").textContent = "Start"; return; }
  if(job.status === "error"){
    $("results").innerHTML = `<p class="err">Error: ${esc(job.error || "unknown")}</p>`;
    $("go").disabled = false; $("go").textContent = "Start"; return;
  }
  timer = setTimeout(() => poll(jobId), 1000);
}
$("f").addEventListener("submit", async e => {
  e.preventDefault();
  const topic = $("topic").value.trim();
  if(!topic) return;
  if(timer) clearTimeout(timer);
  $("go").disabled = true; $("go").textContent = "Running…";
  $("results").innerHTML = "";
  const res = await fetch("/workflow/creator-research", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({topic, max_videos: 3})});
  const data = await res.json();
  if(!res.ok){ $("results").innerHTML = `<p class="err">Error: ${esc(data.detail || data.error || res.status)}</p>`; $("go").disabled = false; $("go").textContent = "Start"; return; }
  const url = new URL(location); url.searchParams.set("topic", topic);
  history.replaceState(null, "", url);
  poll(data.job_id);
});
(function init(){
  const p = new URLSearchParams(location.search);
  const t = p.get("topic") || "";
  if(t) $("topic").value = t;
  if(p.get("autorun") === "1" && t) $("f").dispatchEvent(new Event("submit", {cancelable: true}));
})();
</script></body></html>"""


@app.get("/research", response_class=HTMLResponse)
def research_page():
    return RESEARCH_HTML
