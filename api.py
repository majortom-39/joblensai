"""
JobLens FastAPI Server
Wraps the LangGraph workflow with async execution and per-step progress tracking.

Endpoints:
  POST /analyze         — upload resume + titles, starts background job
  GET  /status/{job_id} — poll step-by-step progress
  GET  /results/{job_id}— retrieve final mapped JobListing array
"""

import json
import threading
import traceback
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from tools.text_extractor import extract_text

app = FastAPI(title="JobLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory job store
# {job_id: {status, steps, results, error}}
# ---------------------------------------------------------------------------

jobs_store: Dict[str, dict] = {}

STEP_DEFINITIONS = [
    {"id": "1", "name": "Job Acquisition Agent",
     "description": "AI suggests job titles from resume; scraping and scoring until 10+ jobs with relevancy >= 85"},
    {"id": "2", "name": "Resume Optimizer",
     "description": "Generating tailored resume suggestions for each matched job"},
    {"id": "3", "name": "Project Ideas Agent",
     "description": "Researching portfolio project ideas and calculating score improvement"},
]


def _init_steps() -> List[dict]:
    return [
        {**s, "status": "pending", "duration": None, "logs": []}
        for s in STEP_DEFINITIONS
    ]


def _set_step(job_id: str, idx: int, status: str, duration: Optional[str] = None):
    """Update a single step's status in the store."""
    if job_id not in jobs_store:
        return
    step = jobs_store[job_id]["steps"][idx]
    step["status"] = status
    if duration:
        step["duration"] = duration


def _add_step_log(job_id: str, step_idx: int, message: str):
    """Append a log entry to a specific step, visible inline in the timeline."""
    if job_id not in jobs_store:
        return
    jobs_store[job_id]["steps"][step_idx]["logs"].append(message)


# ---------------------------------------------------------------------------
# Data mapper: backend job dict -> frontend JobListing shape
# ---------------------------------------------------------------------------

def _parse_projects(projects_text: str, job: dict, idx: int) -> list:
    """Parse structured JSON project suggestions into frontend ProjectSuggestion objects."""
    if not projects_text or projects_text in ("[]", "No project suggestions available.", "No project suggestions generated."):
        return []

    score_boost = max(1, job.get("improvement_potential", 5))
    per_project_boost = max(1, score_boost // 3) if score_boost > 3 else score_boost

    text = projects_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("[")
    end = text.rfind("]") + 1

    if start != -1 and end > start:
        try:
            items = json.loads(text[start:end])
            result = []
            for i, proj in enumerate(items):
                if not isinstance(proj, dict):
                    continue
                tech = proj.get("techStack") or proj.get("tech_stack") or []
                if isinstance(tech, str):
                    tech = [t.strip() for t in tech.split(",") if t.strip()]
                steps = proj.get("steps") or []
                if isinstance(steps, str):
                    steps = [s.strip() for s in steps.split("\n") if s.strip()]

                difficulty = proj.get("difficulty", "Intermediate")
                if difficulty not in ("Beginner", "Intermediate", "Advanced"):
                    difficulty = "Intermediate"

                result.append({
                    "id": f"p{idx}_{i}",
                    "title": proj.get("title") or proj.get("name") or f"Project {i+1}",
                    "difficulty": difficulty,
                    "estimatedTime": proj.get("estimatedTime") or proj.get("estimated_time") or "1-2 weeks",
                    "scoreBoost": per_project_boost,
                    "brief": proj.get("brief") or proj.get("description") or proj.get("goal") or "",
                    "explanation": proj.get("explanation") or proj.get("why") or (
                        f"This project helps raise your match score for {job.get('title', 'this role')}."
                    ),
                    "techStack": tech[:8],
                    "steps": steps[:6],
                })
            if result:
                return result
        except (json.JSONDecodeError, Exception):
            pass

    return [{
        "id": f"p{idx}_0",
        "title": f"Portfolio Projects for {job.get('title', 'this role')}",
        "difficulty": "Intermediate",
        "estimatedTime": "1-2 weeks each",
        "scoreBoost": score_boost,
        "brief": projects_text[:500],
        "explanation": (
            f"Implementing these projects is estimated to raise your match score "
            f"from {job.get('score', 50)} to {job.get('future_score', 60)}."
        ),
        "techStack": [],
        "steps": [],
    }]


def _parse_sectioned_suggestions(raw_suggestions: str) -> List[dict]:
    """Parse resume_suggestions that use [Section: ...] or Section: ... format into { section, suggestion } list."""
    import re
    out = []
    for line in (raw_suggestions or "").splitlines():
        line = line.strip().lstrip("\u2022\u25cf-\u2013* ").strip()
        if not line:
            continue
        if line.upper().startswith("## JOB"):
            continue
        match_bracket = re.match(r"\[Section:\s*(.+?)\]\s*(.+)", line, re.IGNORECASE | re.DOTALL)
        match_plain = re.match(r"Section:\s*(.+?)\s+Change\s+", line, re.IGNORECASE)
        if match_bracket:
            section = match_bracket.group(1).strip()
            suggestion = match_bracket.group(2).strip()
            if section and suggestion:
                out.append({"section": section, "suggestion": suggestion})
        elif match_plain:
            section = match_plain.group(1).strip()
            suggestion = line[match_plain.end(0):].strip() if match_plain.end(0) < len(line) else line
            if section and suggestion:
                out.append({"section": section, "suggestion": suggestion})
        elif re.search(r"Change\s+['\"].+?['\"]\s+to\s+", line, re.IGNORECASE):
            out.append({"section": "Resume", "suggestion": line})
        else:
            if out and not (line.startswith("[") or re.match(r"Section:\s*", line, re.IGNORECASE)):
                out[-1]["suggestion"] = (out[-1]["suggestion"] + " " + line).strip()
            else:
                out.append({"section": "Resume", "suggestion": line})
    return out


def _fallback_sectioned_from_raw(raw_suggestions: str) -> List[dict]:
    """When sectioned parsing returns nothing, build sectioned list from non-empty lines (exclude ## JOB headers)."""
    out = []
    for line in (raw_suggestions or "").splitlines():
        line = line.strip().lstrip("\u2022\u25cf-\u2013* ").strip()
        if not line or line.upper().startswith("## JOB"):
            continue
        out.append({"section": "Resume", "suggestion": line})
    return out


def _map_job(job: dict, idx: int) -> dict:
    """Map a scored_jobs entry to the frontend JobListing interface."""

    raw_suggestions = job.get("resume_suggestions", "") or ""
    sectioned = _parse_sectioned_suggestions(raw_suggestions)
    if not sectioned and raw_suggestions.strip():
        sectioned = _fallback_sectioned_from_raw(raw_suggestions)
    bullet_suggestions = [
        line.lstrip("\u2022\u25cf-\u2013 ").strip()
        for line in raw_suggestions.splitlines()
        if line.strip() and any(line.strip().startswith(c) for c in ("\u2022", "\u25cf", "-", "\u2013", "*"))
    ]
    if not bullet_suggestions and raw_suggestions.strip():
        bullet_suggestions = [s.strip() for s in raw_suggestions.split("\n\n") if s.strip()][:5]
        if not bullet_suggestions:
            bullet_suggestions = [line.strip() for line in raw_suggestions.splitlines() if line.strip() and not line.strip().upper().startswith("## JOB")][:5]
    if not bullet_suggestions and sectioned:
        bullet_suggestions = [item["suggestion"] for item in sectioned]

    projects_text = job.get("project_suggestions", "") or ""
    suggested_projects = _parse_projects(projects_text, job, idx)

    posted_at = job.get("posted_at") or ""
    posted_display = (job.get("posted_display") or "").strip()
    posted_date_display = "Recently"
    if posted_display:
        posted_date_display = posted_display
    elif posted_at:
        try:
            from datetime import datetime, date
            dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            d = dt.date() if hasattr(dt, "date") else date.fromisoformat(posted_at[:10])
            today = date.today()
            delta_days = (today - d).days
            if delta_days == 0:
                posted_date_display = "Today"
            elif delta_days == 1:
                posted_date_display = "1 day ago"
            elif delta_days < 7:
                posted_date_display = f"{delta_days} days ago"
            else:
                posted_date_display = dt.strftime("%b %d") if hasattr(dt, "strftime") else (posted_at[:10] if len(posted_at) >= 10 else "Recently")
        except Exception:
            posted_date_display = posted_at[:10] if len(posted_at) >= 10 else "Recently"

    result = {
        "id": str(idx),
        "title": job.get("title") or "",
        "company": job.get("company") or "",
        "location": job.get("location") or "",
        "type": "Full-time",
        "salary": job.get("salary") or "",
        "relevanceScore": job.get("score", 50),
        "postedDate": posted_date_display,
        "posted_at": posted_at,
        "description": (job.get("description") or "")[:600],
        "relevanceSummary": (job.get("brief_relevance_summary") or "").strip() or None,
        "url": job.get("url") or "",
        "source": job.get("source") or "",
        "bulletSuggestions": bullet_suggestions,
        "suggestedProjects": suggested_projects,
        "futureScore": job.get("future_score", 0),
        "improvementPotential": job.get("improvement_potential", 0),
        "saved": False,
        "applied": False,
    }
    if sectioned:
        result["bulletSuggestionsBySection"] = sectioned
    return result


# ---------------------------------------------------------------------------
# Background worker — LangGraph agentic workflow
# ---------------------------------------------------------------------------

import time as _time


def _run_workflow(
    job_id: str,
    resume_text: str,
    cover_letter_text: str,
    desired_titles: List[str],
    job_type: str = "full_time",
):
    """
    Runs the LangGraph workflow. AI suggests job titles based on job_type.
    Three steps: Phase 1 (decide titles + scrape/score loop), Phase 2 (resume modifier),
    Phase 3 (project proposer + future scores + relevance summary).
    """
    try:
        from agents.v3_graph import build_v3_workflow
        from agents.state import V3State

        _last_phase = [0]

        def log_cb(state, msg):
            step_idx = state.get("_log_phase", 0)
            if step_idx != _last_phase[0]:
                _set_step(job_id, _last_phase[0], "completed")
                _set_step(job_id, step_idx, "running")
                _last_phase[0] = step_idx
            _add_step_log(job_id, step_idx, msg)

        initial_state: V3State = {
            "resume": resume_text,
            "cover_letter": cover_letter_text,
            "job_type": job_type,
            "suggested_titles": [],
            "qualifying_jobs": [],
            "seen_urls": [],
            "current_batch": [],
            "phase1_last_tool_call": None,
            "last_scrape_result_count": 0,
            "last_qualifying_added_count": 0,
            "last_tried_title": "",
            "last_tried_page": -1,
            "phase1_tried_pairs": [],
            "phase1_rounds": 0,
            "phase2_rounds": 0,
            "_log": log_cb,
            "_log_phase": 0,
        }

        _set_step(job_id, 0, "running")
        t0 = _time.time()

        app = build_v3_workflow()
        final_state = app.invoke(initial_state)

        for idx in range(3):
            _set_step(job_id, idx, "completed", f"{_time.time()-t0:.1f}s" if idx == 0 else None)

        qualifying_jobs = final_state.get("qualifying_jobs") or []
        qualifying_jobs.sort(key=lambda x: x.get("improvement_potential", 0), reverse=True)

        jobs_store[job_id]["results"] = [
            _map_job(job, i + 1) for i, job in enumerate(qualifying_jobs)
        ]
        jobs_store[job_id]["status"] = "completed"
        _add_step_log(job_id, 2, f"Done! {len(qualifying_jobs)} jobs ready for review.")

    except Exception as exc:
        err_msg = f"Workflow error: {exc}"
        print(f"[API] {err_msg}", flush=True)
        traceback.print_exc()
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        for step in jobs_store.get(job_id, {}).get("steps", []):
            if step.get("status") == "running":
                idx = jobs_store[job_id]["steps"].index(step)
                _add_step_log(job_id, idx, f"ERROR: {err_msg}")
                step["status"] = "error"
        if job_id in jobs_store:
            jobs_store[job_id]["status"] = "error"
            jobs_store[job_id]["error"] = str(exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze")
async def analyze(
    resume: UploadFile = File(...),
    cover_letter: Optional[UploadFile] = None,
    job_titles: str = Form("[]"),
    job_type: str = Form("full_time"),
):
    """
    Accept resume + optional cover letter upload.
    Starts the workflow in a background thread and returns a job_id.
    """
    print(f"[API] POST /analyze received", flush=True)
    try:
        resume_bytes = await resume.read()
        if not resume_bytes:
            raise HTTPException(status_code=400, detail="Resume file is empty.")
        resume_filename = resume.filename or "resume.pdf"
        print(f"[API] Resume received: {resume_filename} ({len(resume_bytes):,} bytes)", flush=True)
        resume_text = extract_text(resume_bytes, resume_filename)
        print(f"[API] Resume text extracted: {len(resume_text):,} chars", flush=True)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[API] Resume extraction error: {exc}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Could not extract text from resume: {exc}")

    cover_letter_text = ""
    if cover_letter is not None:
        try:
            cl_filename = cover_letter.filename or ""
            if cl_filename:
                cl_bytes = await cover_letter.read()
                if cl_bytes:
                    cover_letter_text = extract_text(cl_bytes, cl_filename)
                    print(f"[API] Cover letter extracted: {len(cover_letter_text):,} chars", flush=True)
        except Exception as exc:
            print(f"[API] Cover letter extraction error (ignoring): {exc}", flush=True)

    try:
        desired_titles: List[str] = json.loads(job_titles)
    except (json.JSONDecodeError, ValueError):
        desired_titles = []

    job_type_val = job_type if job_type in ("full_time", "internship", "both") else "full_time"

    job_id = str(uuid.uuid4())
    jobs_store[job_id] = {
        "status": "running",
        "steps": _init_steps(),
        "results": None,
        "error": None,
    }

    thread = threading.Thread(
        target=_run_workflow,
        args=(job_id, resume_text, cover_letter_text, desired_titles, job_type_val),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Return current status and step-by-step progress for a job."""
    entry = jobs_store.get(job_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": entry["status"],
        "steps": entry["steps"],
        "error": entry.get("error"),
    }


@app.get("/results/{job_id}")
def get_results(job_id: str):
    """Return the final mapped JobListing array once the workflow is complete."""
    entry = jobs_store.get(job_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Job not found")
    if entry["status"] != "completed":
        raise HTTPException(status_code=202, detail="Workflow not yet complete")
    return {"jobs": entry["results"] or []}


@app.get("/health")
def health():
    return {"status": "ok"}
