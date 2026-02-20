"""
V3 Agentic Workflow — Full LangGraph
Phase 1: Gemini decides job titles, then agent loops (scraper tool + score) until 10+ jobs with score >= 85.
Phase 2: Resume modifier (with search) generates tailored suggestions per job.
Phase 3: Project proposer (with search) + future scores.
"""

import json
import os
import re
import sys
import time
from typing import Any, Callable, Dict, List, Literal, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import END, StateGraph

from agents.state import V3State
from config import GEMINI_API_KEY, get_model_name
from tools.scraper import scrape_jobs
from tools.file_manager import update_relevant_jobs

# V3 constants
V3_SCORE_THRESHOLD = 85
V3_TARGET_QUALIFYING_JOBS = 10
V3_PHASE1_MAX_ROUNDS = 15
COOLDOWN_SECONDS = 4
BATCH_SIZE = 3

# Full resume/cover letter for prompts (high caps so all sections are included)
V3_MAX_RESUME_CHARS: Optional[int] = 50_000
V3_MAX_COVER_LETTER_CHARS: Optional[int] = 15_000


def _resume_for_prompt(resume: str) -> str:
    """Return full resume for prompt, up to safety cap. Consider all sections including Projects."""
    if not resume:
        return ""
    if V3_MAX_RESUME_CHARS is None:
        return resume
    return resume[:V3_MAX_RESUME_CHARS] if len(resume) > V3_MAX_RESUME_CHARS else resume


def _cover_for_prompt(cover: str) -> str:
    """Return full cover letter for prompt, up to safety cap."""
    if not cover:
        return ""
    text = (cover or "").strip()
    if not text:
        return ""
    if V3_MAX_COVER_LETTER_CHARS is None:
        return text
    return text[:V3_MAX_COVER_LETTER_CHARS] if len(text) > V3_MAX_COVER_LETTER_CHARS else text


# ---------------------------------------------------------------------------
# Helpers: Gemini client, rate limit, JSON parse
# ---------------------------------------------------------------------------

def _get_client():
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


_last_call_ts: float = 0.0


def _rate_limited_gemini(
    prompt: str,
    max_attempts: int = 3,
    use_search_grounding: bool = False,
    config_extra: Optional[Any] = None,
) -> str:
    global _last_call_ts
    from google.genai import types
    client = _get_client()
    for attempt in range(max_attempts):
        elapsed = time.time() - _last_call_ts
        if elapsed < COOLDOWN_SECONDS:
            time.sleep(COOLDOWN_SECONDS - elapsed)
        try:
            cfg = config_extra
            if not cfg:
                cfg = types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ) if use_search_grounding else None
            _last_call_ts = time.time()
            r = client.models.generate_content(
                model=get_model_name(use_fallback=attempt >= 2),
                contents=prompt,
                config=cfg,
            )
            return r.text or ""
        except Exception as e:
            if "429" in str(e) and attempt < max_attempts - 1:
                time.sleep(COOLDOWN_SECONDS * (2 ** attempt))
            else:
                if attempt == max_attempts - 1:
                    print(f"[V3] Gemini failed: {str(e)[:120]}", flush=True)
                time.sleep(COOLDOWN_SECONDS)
    return ""


def _extract_json_array(text: str) -> List[Dict]:
    """Parse a JSON array from model output. Tolerates markdown and minor malformations."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 1)[1]
        if t.startswith("json"):
            t = t[4:]
    start = t.find("[")
    if start == -1:
        return []
    # Find matching closing bracket so we don't include trailing text or a second array
    depth = 0
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(t)):
        c = t[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if in_string:
            if c == in_string:
                in_string = False
            continue
        if c in ('"', "'"):
            in_string = c
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end <= start:
        end = t.rfind("]") + 1
    if end <= start:
        return []
    raw = t[start:end]
    # Fix common model mistakes: missing comma between } and {
    raw = re.sub(r"\}\s*\n\s*\{", "},{", raw)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    return []


def _extract_json_string_array(text: str) -> List[str]:
    """Parse a JSON array of strings, e.g. [\"Title A\", \"Title B\"]."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 1)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("["), t.rfind("]") + 1
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(t[start:end])
        if not isinstance(parsed, list):
            return []
        return [str(x).strip() for x in parsed if x][:5]
    except (json.JSONDecodeError, TypeError):
        return []


def _normalize_function_call_args(fc: Any) -> Dict[str, Any]:
    """Convert Gemini function_call args (may be Struct, dict, or protobuf) to a plain dict."""
    args = getattr(fc, "args", None)
    if args is None:
        return {}
    if isinstance(args, dict):
        return {str(k): v for k, v in args.items()}
    # Protobuf Struct / mapping-like
    out = {}
    for key in ("job_title", "page"):
        val = None
        if hasattr(args, "get"):
            val = args.get(key)
        if val is None and hasattr(args, "__getitem__"):
            try:
                val = args[key]
            except (KeyError, TypeError):
                pass
        if val is None:
            val = getattr(args, key, None)
        if val is not None:
            out[key] = val
    return out


def _log(state: V3State, msg: str):
    fn = state.get("_log")
    if fn:
        try:
            fn(state, msg)
        except TypeError:
            fn(msg)


# ---------------------------------------------------------------------------
# Phase 1: Decide titles
# ---------------------------------------------------------------------------

def decide_titles_node(state: V3State) -> Dict[str, Any]:
    _log(state, "Analyzing resume and cover letter to suggest job titles...")
    resume = _resume_for_prompt(state.get("resume") or "")
    cover = _cover_for_prompt(state.get("cover_letter") or "")
    job_type = (state.get("job_type") or "full_time").strip().lower()
    cl = f"\nCover letter:\n{cover}\n" if cover else ""
    if job_type == "full_time":
        type_instruction = (
            "Output 1 to 3 job titles for FULL-TIME roles only. Do NOT include 'Intern' or 'Internship' in any title. "
            "Examples: \"Product Manager\", \"Data Analyst\", \"Software Engineer\"."
        )
        max_titles = 3
    elif job_type == "internship":
        type_instruction = (
            "Output 1 to 3 job titles for INTERNSHIP roles only. Each title MUST include \"Intern\" or \"Internship\" "
            "(e.g. \"Product Manager Intern\", \"Data Science Intern\", \"Software Engineering Intern\")."
        )
        max_titles = 3
    else:
        type_instruction = (
            "Output 2 to 4 job titles so we get BOTH full-time and internship results. For each role suggest both the "
            "full-time title and the same with ' Intern' (e.g. \"Product Manager\", \"Product Manager Intern\", "
            "\"Data Analyst\", \"Data Analyst Intern\"). Use common LinkedIn phrases."
        )
        max_titles = 4
    prompt = (
        f"Based on this candidate profile, suggest job titles for LinkedIn job search.\n\n"
        f"{type_instruction}\n\n"
        f"=== CANDIDATE RESUME (read ALL sections including Work Experience, Projects, Education, Activities, Skills) ===\n{resume}\n{cl}\n"
        f"IMPORTANT: You MUST consider ALL sections above, including Projects and other roles/experience at the end of the resume.\n\n"
        f"Return ONLY a JSON array of strings. No explanation, no markdown, no code fences."
    )
    text = _rate_limited_gemini(prompt)
    titles: List[str] = _extract_json_string_array(text)
    if not titles and text.strip():
        arr = _extract_json_array(text)
        for x in arr:
            if isinstance(x, dict) and "title" in x:
                titles.append(str(x["title"]).strip())
            elif isinstance(x, dict) and "name" in x:
                titles.append(str(x["name"]).strip())
        if not titles and "[" in text:
            try:
                parsed = json.loads(text[text.find("["):text.rfind("]")+1])
                if isinstance(parsed, list):
                    titles = [str(p).strip() for p in parsed if p][:max_titles]
            except Exception:
                pass
    if not titles:
        titles = ["Software Engineer"] if job_type == "full_time" else ["Software Engineer Intern"]
    titles = [t for t in titles if t][:max_titles]
    _log(state, f"Suggested job titles: {', '.join(titles)}")
    return {"suggested_titles": titles}


# ---------------------------------------------------------------------------
# Phase 1: Scraper tool declaration and execution
# ---------------------------------------------------------------------------

def _scrape_linkedin_tool(job_title: str, page: int) -> List[Dict]:
    """One page of LinkedIn jobs (most recent). Called by Phase 1 agent."""
    title = (job_title or "").strip() or "Software Engineer"
    batch = scrape_jobs(
        job_titles=[title],
        max_jobs=10,
        start_offset=page * 10,
        sort_by="recent",
    )
    out = []
    for j in batch:
        url = j.get("url") or j.get("job_url") or ""
        out.append({
            "title": j.get("title") or "N/A",
            "company": j.get("company") or "N/A",
            "location": j.get("location") or "N/A",
            "description": (j.get("description") or "")[:2000],
            "salary": j.get("salary") or "",
            "url": url,
            "source": j.get("source") or "linkedin",
            "posted_at": j.get("posted_at"),
            "posted_display": j.get("posted_display"),
        })
    return out


def _phase1_tool_declaration():
    from google.genai import types
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="scrape_linkedin",
                description="Scrape one page of LinkedIn job listings for a given job title (most recent first). Call this repeatedly with the same or different titles and incrementing page (0, 1, 2...) until we have enough high-relevance jobs.",
                parameters={
                    "type": "object",
                    "properties": {
                        "job_title": {"type": "string", "description": "Job title to search, e.g. Software Engineer"},
                        "page": {"type": "integer", "description": "Page index (0-based). 0 = first page, 1 = next 10, etc."},
                    },
                    "required": ["job_title"],
                },
            )
        ]
    )


def _tried_pairs_set(tried_pairs: List[Dict[str, Any]]) -> set:
    """Normalize to set of (title, page) for membership checks."""
    out = set()
    for p in tried_pairs or []:
        t = (p.get("title") or "").strip()
        try:
            pg = int(p.get("page", 0))
        except (TypeError, ValueError):
            pg = 0
        if t:
            out.add((t, pg))
    return out


def _get_next_title_page(
    suggested_titles: List[str],
    tried_pairs: List[Dict[str, Any]],
    max_page_per_title: int = 5,
) -> Optional[tuple]:
    """Return (title, page) for the next scrape not yet tried. Order: title0 page 0,1,..., then title1 page 0,1,..., etc."""
    tried = _tried_pairs_set(tried_pairs)
    titles = suggested_titles or ["Software Engineer"]
    for title in titles:
        title = (title or "").strip()
        if not title:
            continue
        for page in range(max_page_per_title + 1):
            if (title, page) not in tried:
                return (title, page)
    return None


def phase1_agent_node(state: V3State) -> Dict[str, Any]:
    suggested = state.get("suggested_titles") or []
    qualifying = state.get("qualifying_jobs") or []
    n = len(qualifying)
    tried_pairs = state.get("phase1_tried_pairs") or []
    tried_set = _tried_pairs_set(tried_pairs)
    titles_str = ", ".join(f'"{t}"' for t in suggested) if suggested else '"Software Engineer"'
    first_title = suggested[0] if suggested else "Software Engineer"

    if n >= V3_TARGET_QUALIFYING_JOBS:
        _log(state, f"Collected {n} qualifying jobs (target {V3_TARGET_QUALIFYING_JOBS}). Moving to Phase 2.")
        return {"phase1_last_tool_call": None}

    next_pair = _get_next_title_page(suggested, tried_pairs)
    if not next_pair:
        _log(state, f"All (title, page) combinations exhausted. Moving to Phase 2 with {n} jobs.")
        return {"phase1_last_tool_call": None}

    # Build rich scrape history for the LLM
    history_lines = []
    for p in tried_pairs:
        t = p.get("title", "?")
        pg = p.get("page", 0)
        scraped = p.get("jobs_returned", "?")
        added = p.get("qualifying_added", "?")
        history_lines.append(f"  - scrape_linkedin(\"{t}\", page={pg}) -> {scraped} jobs returned, {added} qualified")
    history_block = "\n".join(history_lines) if history_lines else "  (none yet — this is the first search)"

    prompt = (
        f"You are a job search agent with access to the scrape_linkedin tool. Your goal is to collect at least "
        f"{V3_TARGET_QUALIFYING_JOBS} highly relevant jobs (score >= {V3_SCORE_THRESHOLD}) for this candidate.\n\n"
        f"Available job titles to search: [{titles_str}]\n\n"
        f"=== SEARCH HISTORY ===\n{history_block}\n\n"
        f"=== CURRENT STATUS ===\n"
        f"Qualifying jobs so far: {n} / {V3_TARGET_QUALIFYING_JOBS}\n"
        f"Remaining to collect: {V3_TARGET_QUALIFYING_JOBS - n}\n\n"
        f"=== RULES ===\n"
        f"1. You MUST call scrape_linkedin with a (job_title, page) you have NOT used before (see history above).\n"
        f"2. For each title, progress through pages: 0, then 1, then 2, etc.\n"
        f"3. If a title's last page returned few/no results, switch to a different title.\n"
        f"4. Use ONLY titles from the list above.\n\n"
        f"Decide your next search and call scrape_linkedin now.\n"
    )

    from google.genai import types
    global _last_call_ts
    client = _get_client()
    elapsed = time.time() - _last_call_ts
    if elapsed < COOLDOWN_SECONDS:
        time.sleep(COOLDOWN_SECONDS - elapsed)
    try:
        _last_call_ts = time.time()
        r = client.models.generate_content(
            model=get_model_name(),
            contents=prompt,
            config=types.GenerateContentConfig(tools=[_phase1_tool_declaration()]),
        )
    except Exception as e:
        print(f"[V3] Phase1 agent call failed: {e}", flush=True)
        return {"phase1_last_tool_call": None}

    fc = None
    if r.candidates and r.candidates[0].content and r.candidates[0].content.parts:
        for part in r.candidates[0].content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                break
    if fc and getattr(fc, "name", None) == "scrape_linkedin":
        args = _normalize_function_call_args(fc)
        if not args:
            raw_args = getattr(fc, "args", None)
            if raw_args is not None:
                try:
                    if hasattr(raw_args, "items"):
                        args = dict(raw_args)
                    elif hasattr(raw_args, "keys"):
                        args = {k: raw_args[k] for k in raw_args.keys()}
                except Exception:
                    pass
        raw_title = args.get("job_title") or first_title
        job_title = str(raw_title).strip() if raw_title else first_title
        if suggested and job_title not in suggested:
            job_title = first_title
        try:
            page = int(args.get("page", 0))
        except (TypeError, ValueError):
            page = 0

        # Safety net: if LLM picked a (title, page) already tried, override deterministically
        if (job_title, page) in tried_set:
            override_title, override_page = next_pair
            _log(state, f"Agent picked already-tried ({job_title!r}, {page}); overriding to ({override_title!r}, {override_page})")
            job_title, page = override_title, override_page

        _log(state, f"Agent calling scrape_linkedin({job_title!r}, page={page})")
        return {"phase1_last_tool_call": {"name": "scrape_linkedin", "args": {"job_title": job_title, "page": page}}}
    return {"phase1_last_tool_call": None}


def phase1_tool_node(state: V3State) -> Dict[str, Any]:
    tool = state.get("phase1_last_tool_call")
    if not tool or tool.get("name") != "scrape_linkedin":
        return {"current_batch": [], "phase1_last_tool_call": None, "phase1_tried_pairs": state.get("phase1_tried_pairs") or []}
    args = tool.get("args") or {}
    suggested = state.get("suggested_titles") or []
    job_title = (args.get("job_title") or "").strip()
    if not job_title or (suggested and job_title not in suggested):
        job_title = suggested[0] if suggested else "Software Engineer"
        _log(state, f"Using suggested title for scraper: {job_title!r}")
    try:
        page = int(args.get("page", 0))
    except (TypeError, ValueError):
        page = 0
    seen = list(state.get("seen_urls") or [])
    batch = _scrape_linkedin_tool(job_title, page)
    fresh = []
    for j in batch:
        url = j.get("url") or ""
        if url and url not in seen:
            seen.append(url)
            fresh.append(j)
    if fresh:
        _log(state, f"Scraped {len(fresh)} new jobs (page {page}, title {job_title!r})")
    else:
        _log(state, f"Scraped 0 new jobs for {job_title!r} page {page}")
    existing_tried = list(state.get("phase1_tried_pairs") or [])
    existing_tried.append({"title": job_title, "page": page, "jobs_returned": len(fresh)})
    return {
        "current_batch": fresh,
        "seen_urls": seen,
        "phase1_last_tool_call": None,
        "last_tried_title": job_title,
        "last_tried_page": page,
        "phase1_tried_pairs": existing_tried,
    }


def score_batch_node(state: V3State) -> Dict[str, Any]:
    batch = state.get("current_batch") or []
    tried_pairs = list(state.get("phase1_tried_pairs") or [])
    if not batch:
        return {"current_batch": [], "last_scrape_result_count": 0, "last_qualifying_added_count": 0, "phase1_tried_pairs": tried_pairs}

    resume = _resume_for_prompt(state.get("resume") or "")
    cover = _cover_for_prompt(state.get("cover_letter") or "")
    cl_section = f"\nCover letter:\n{cover}\n" if cover else ""
    jobs_for_prompt = [
        {"idx": i, "title": j.get("title", "N/A"), "company": j.get("company", "N/A"),
         "location": j.get("location", "N/A"), "description": (j.get("description") or "")[:350], "salary": j.get("salary", "")}
        for i, j in enumerate(batch)
    ]
    prompt = (
        f"Score each job 0-100 for relevance to this candidate.\n\n"
        f"Jobs:\n{json.dumps(jobs_for_prompt, indent=1)}\n\n"
        f"=== CANDIDATE RESUME (read ALL sections including Work Experience, Projects, Education, Activities, Skills) ===\n{resume}\n{cl_section}\n"
        f"IMPORTANT: You MUST consider ALL sections of the resume above, including Projects and other roles/experience at the end.\n\n"
        f"Return ONLY a JSON array: [{{\"idx\": 0, \"score\": 85}}, ...]. No explanation."
    )
    _log(state, f"Scoring {len(batch)} jobs...")
    text = _rate_limited_gemini(prompt)
    score_map = {}
    if text.strip():
        for s in _extract_json_array(text):
            idx = s.get("idx")
            sc = s.get("score", 0)
            if idx is not None:
                try:
                    score_map[int(idx)] = max(0, min(100, int(sc)))
                except (ValueError, TypeError):
                    pass
    qualifying_jobs = list(state.get("qualifying_jobs") or [])
    added = 0
    for i, j in enumerate(batch):
        sc = score_map.get(i, 70)
        j["score"] = sc
        if sc >= V3_SCORE_THRESHOLD:
            qualifying_jobs.append(j)
            added += 1
    _log(state, f"Added {added} qualifying jobs (total {len(qualifying_jobs)})")
    rounds = (state.get("phase1_rounds") or 0) + 1
    # Enrich the latest tried_pairs entry with how many qualified from this batch
    if tried_pairs:
        tried_pairs[-1]["qualifying_added"] = added
    return {
        "qualifying_jobs": qualifying_jobs,
        "current_batch": [],
        "last_scrape_result_count": len(batch),
        "last_qualifying_added_count": added,
        "phase1_rounds": rounds,
        "phase1_tried_pairs": tried_pairs,
    }


def phase1_route(state: V3State) -> Literal["phase1_tools", "resume_modifier_agent", "phase1_agent"]:
    qualifying = state.get("qualifying_jobs") or []
    if len(qualifying) >= V3_TARGET_QUALIFYING_JOBS:
        return "resume_modifier_agent"
    if state.get("phase1_rounds", 0) >= V3_PHASE1_MAX_ROUNDS:
        return "resume_modifier_agent"
    if state.get("phase1_last_tool_call"):
        return "phase1_tools"
    return "phase1_agent"


# ---------------------------------------------------------------------------
# Phase 2: Resume modifier (generates tailored suggestions per job)
# ---------------------------------------------------------------------------

def _batch_writer_prompt(jobs_batch: List[Dict], resume_text: str, cover_letter_text: str) -> str:
    resume = _resume_for_prompt(resume_text or "")
    cover = _cover_for_prompt(cover_letter_text or "")
    cl = f"\nCover letter:\n{cover}\n" if cover else ""
    jobs_section = ""
    for i, job in enumerate(jobs_batch):
        jobs_section += f"\n--- JOB {i+1} ---\nTitle: {job.get('title', 'N/A')}\nCompany: {job.get('company', 'N/A')}\nDescription:\n{(job.get('description') or '')[:1500]}\n"
    base = (
        f"You are a senior resume strategist who understands what hiring managers and ATS systems look for.\n\n"
        f"GOAL: For each job below, suggest 2-4 targeted modifications to EXISTING lines in the candidate's resume "
        f"that would make the resume significantly more compelling for that specific role.\n\n"
        f"RULES:\n"
        f"- You may ONLY modify text that already exists in the resume. Every 'original' phrase MUST come from the resume below.\n"
        f"- Do NOT copy phrases from the job description as the 'original'. Do NOT invent new bullet points.\n"
        f"- Prioritize changes that close the BIGGEST gaps between the resume and the job requirements.\n"
        f"- Think like the hiring manager: what would make them stop and say 'this person is a fit'?\n\n"
        f"WHAT MAKES A GOOD SUGGESTION:\n"
        f"- Reframing a generic achievement to highlight the specific skill/domain the job demands.\n"
        f"- Adding quantifiable results (metrics, scale, percentages) to vague statements.\n"
        f"- Surfacing relevant experience that is buried or understated — especially from Projects, Activities, or secondary roles.\n"
        f"- Aligning terminology with the role's domain without keyword-stuffing (the result must read naturally).\n\n"
        f"WHAT TO AVOID:\n"
        f"- Do NOT suggest trivially adding a buzzword. Every change must strengthen the narrative for this role.\n"
        f"- Do NOT suggest changes that would make the resume dishonest or exaggerate beyond what the original implies.\n"
        f"- Do NOT repeat the same suggestion for multiple jobs if they serve different needs.\n\n"
        f"FORMAT: Start each job's block with exactly ## JOB 1, ## JOB 2, etc. (required for parsing).\n"
        f"Each suggestion line MUST use this format:\n"
        f"   [Section: <section name>] Change '<exact or near-exact original from resume>' to '<improved version>' because <reason tied to the specific job requirement it addresses>\n\n"
        f"Example:\n"
        f"   [Section: Work Experience – Acme Corp] Change 'Led cross-functional team on product launches' to "
        f"'Led cross-functional team of 8 across engineering, design, and marketing to ship 3 B2B SaaS features, increasing enterprise adoption by 20%' "
        f"because the role requires B2B SaaS product leadership with measurable business impact.\n\n"
        f"If you cannot identify the section, use: [Section: Resume]\n\n"
        f"=== TARGET JOBS ===\n{jobs_section}\n\n"
    )
    base += (
        f"=== CANDIDATE RESUME (use ONLY this text for 'original' phrases — read ALL sections including Work Experience, Projects, Education, Activities, Skills) ===\n{resume}\n{cl}\n"
        f"IMPORTANT: Read the ENTIRE resume top to bottom. Sections near the end (Projects, Activities, Education) often contain "
        f"highly relevant experience that can be reframed for these roles. Do not skip them."
    )
    return base




def _split_batch_suggestions(text: str, count: int) -> List[str]:
    parts = [""] * count
    tu = text.upper()

    def try_markers(markers: List[str]) -> bool:
        for i, marker in enumerate(markers):
            start = tu.find(marker.upper())
            if start == -1:
                continue
            start += len(marker)
            end = tu.find(markers[i + 1].upper()) if i + 1 < len(markers) else len(text)
            if i + 1 < len(markers) and end == -1:
                end = len(text)
            chunk = text[start:end].strip()
            if len(chunk) > 20:
                parts[i] = chunk
        return bool(any(parts))

    # Try ## JOB N and ### JOB N first
    if try_markers([f"## JOB {i+1}" for i in range(count)]):
        return parts
    parts = [""] * count
    if try_markers([f"### JOB {i+1}" for i in range(count)]):
        return parts
    parts = [""] * count
    # Lenient: JOB 1, Job 1:, **Job 1**, or line starting with "1." "2." etc.
    for i in range(count):
        n = i + 1
        patterns = [
            f"JOB {n}:",
            f"JOB {n}\n",
            f"JOB {n} ",
            f"**JOB {n}**",
            f"**Job {n}**",
            f"Job {n}:",
            f"Job {n}\n",
        ]
        for pat in patterns:
            start = tu.find(pat.upper())
            if start != -1:
                start += len(pat)
                end = len(text)
                for j in range(i + 1, count):
                    next_pat = f"JOB {j+1}"
                    pos = tu.find(next_pat.upper(), start)
                    if pos != -1:
                        end = pos
                        break
                chunk = text[start:end].strip()
                if len(chunk) > 20:
                    parts[i] = chunk
                break
    if any(parts):
        return parts

    # Fallback: no headers found but text is non-empty
    stripped = text.strip()
    if not stripped:
        return parts
    if count == 1:
        parts[0] = stripped
        return parts
    # Split by double newline and assign to jobs in order
    chunks = [c.strip() for c in stripped.split("\n\n") if c.strip()]
    if not chunks:
        parts[0] = stripped
        return parts
    for i in range(min(count, len(chunks))):
        if len(chunks[i]) > 20:
            parts[i] = chunks[i]
    if len(chunks) > count:
        parts[count - 1] = "\n\n".join(chunks[count - 1 :])
    return parts


def resume_modifier_agent_node(state: V3State) -> Dict[str, Any]:
    jobs = state.get("qualifying_jobs") or []
    resume = state.get("resume") or ""
    cover = (state.get("cover_letter") or "")
    state["_log_phase"] = 1
    total_batches = (len(jobs) + BATCH_SIZE - 1) // BATCH_SIZE
    _log(state, f"Resume Optimizer: starting — {len(jobs)} jobs in {total_batches} batch(es).")
    for batch_start in range(0, len(jobs), BATCH_SIZE):
        batch_idx = batch_start // BATCH_SIZE + 1
        batch = jobs[batch_start:batch_start + BATCH_SIZE]
        job_range = f"jobs {batch_start + 1}–{batch_start + len(batch)}"
        _log(state, f"Resume Optimizer: batch {batch_idx}/{total_batches} — generating suggestions for {job_range} (with web search)...")
        prompt = _batch_writer_prompt(batch, resume, cover)
        text = _rate_limited_gemini(prompt, use_search_grounding=True)
        if not text.strip():
            for j in batch:
                j["resume_suggestions"] = "No suggestions generated."
            _log(state, f"Resume Optimizer: batch {batch_idx}/{total_batches} — no output; using fallback.")
            continue
        parts = _split_batch_suggestions(text, len(batch))
        for i, j in enumerate(batch):
            j["resume_suggestions"] = (parts[i] if i < len(parts) and parts[i] else "").strip() or "No suggestions generated."
        _log(state, f"Resume Optimizer: batch {batch_idx}/{total_batches} — suggestions generated for {job_range}.")
    _log(state, "Resume Optimizer: all suggestion batches complete.")
    return {"qualifying_jobs": jobs, "_log_phase": 1}




# ---------------------------------------------------------------------------
# Phase 3: Project proposer + future scores
# ---------------------------------------------------------------------------

def _batch_projects_prompt(jobs: List[Dict], resume_text: str, cover_letter_text: str) -> str:
    resume = _resume_for_prompt(resume_text or "")
    cover = _cover_for_prompt(cover_letter_text or "")
    cl = f"\nCover letter:\n{cover}\n" if cover else ""
    jobs_section = ""
    for i, j in enumerate(jobs):
        desc = (j.get("description") or "")[:1500]
        title = j.get("title", "N/A")
        company = j.get("company", "N/A")
        gaps = (j.get("resume_suggestions") or "")[:800]
        jobs_section += f"\n--- JOB {i} ---\nTitle: {title}\nCompany: {company}\nFull description:\n{desc}\nResume improvement suggestions for this role:\n{gaps}\n"
    return (
        f"You are a portfolio strategist who helps candidates build targeted proof-of-work projects that make hiring managers take notice.\n\n"
        f"CONTEXT: The candidate is applying to the jobs below. For each job, resume improvement suggestions have already been generated. "
        f"Your role is to propose portfolio micro-projects that go BEYOND resume rewording — these projects give the candidate "
        f"tangible, demonstrable evidence of skills they currently lack on paper.\n\n"
        f"CONSTRAINTS:\n"
        f"- The candidate has NO access to the company's internal systems, data, or proprietary information.\n"
        f"- Each project must use ONLY: public datasets, open APIs, synthetic/sample data, or the candidate's own generated data.\n"
        f"- Each project must be completable in 1-2 weeks and produce a concrete deliverable (GitHub repo, deployed app/dashboard, published write-up, or similar).\n\n"
        f"YOUR APPROACH:\n"
        f"1. Read the job description to understand what business problem/domain the company cares about.\n"
        f"2. Read the candidate's FULL resume (all sections) to understand what they ALREADY have — skills, projects, and experience.\n"
        f"3. Identify the 1-3 most impactful gaps: what does this role need that the candidate cannot currently demonstrate?\n"
        f"4. For each gap, design a project that:\n"
        f"   - Mirrors a realistic problem in that company's domain (not a generic tutorial project).\n"
        f"   - Produces a portfolio piece the candidate can LINK TO on their resume or cover letter.\n"
        f"   - Uses a specific, named data source (e.g. 'Use the UCI Online Retail dataset from Kaggle' or 'Pull live data from the Twitter/X API').\n"
        f"   - Includes clear steps so the candidate knows exactly what to build.\n\n"
        f"DO NOT:\n"
        f"- Suggest projects the candidate has ALREADY built (check their Projects section).\n"
        f"- Suggest generic projects like 'build a to-do app' or 'create a dashboard'. Every project must be specific to the job's domain.\n"
        f"- Suggest projects that only prove skills the candidate already demonstrates on their resume.\n\n"
        f"=== TARGET JOBS ===\n{jobs_section}\n\n"
        f"=== CANDIDATE RESUME (read ALL sections including Work Experience, Projects, Education, Activities, Skills) ===\n{resume}\n{cl}\n"
        f"IMPORTANT: Read the ENTIRE resume. The Projects and Activities sections tell you what the candidate has ALREADY built — do not suggest duplicates.\n\n"
        f"Return ONLY a JSON array. Each element: {{\"idx\": <job index 0-based>, \"projects\": [{{\"title\": \"...\", \"difficulty\": \"Beginner\"|\"Intermediate\"|\"Advanced\", "
        f"\"estimatedTime\": \"1-2 weeks\", \"brief\": \"One-line summary of what the candidate will build and why it matters for this role.\", "
        f"\"explanation\": \"2-3 sentences: what specific gap this fills, how it relates to the company's domain, and what the deliverable is.\", "
        f"\"techStack\": [\"tool1\", \"tool2\"], \"steps\": [\"Step 1: ...\", \"Step 2: ...\", ...]}}]}}. No markdown."
    )


def _batch_future_scores_prompt(jobs: List[Dict], resume_text: str, cover_letter_text: str) -> str:
    resume = _resume_for_prompt(resume_text or "")
    cover = _cover_for_prompt(cover_letter_text or "")
    cl = f"\nCover letter:\n{cover}\n" if cover else ""
    jobs_section = "\n".join(
        f'{{"idx": {i}, "title": "{j.get("title", "N/A")}", "current_score": {j.get("score", 50)}, '
        f'"resume_improvements": "{(j.get("resume_suggestions") or "")[:100]}", "projects_planned": "{(j.get("project_suggestions") or "")[:100]}"}}'
        for i, j in enumerate(jobs)
    )
    return (
        f"Predict NEW match score (0-100) after resume improvements and portfolio projects.\n\n"
        f"Jobs:\n{jobs_section}\n\n"
        f"=== CANDIDATE RESUME (read ALL sections including Work Experience, Projects, Education, Activities, Skills) ===\n{resume}\n{cl}\n"
        f"IMPORTANT: Consider ALL sections of the resume above.\n\n"
        f"Return ONLY a JSON array: [{{\"idx\": 0, \"future_score\": 92}}, ...]. No markdown."
    )


def project_proposer_node(state: V3State) -> Dict[str, Any]:
    jobs = state.get("qualifying_jobs") or []
    resume = state.get("resume") or ""
    cover = state.get("cover_letter") or ""
    state["_log_phase"] = 2
    total_batches = (len(jobs) + BATCH_SIZE - 1) // BATCH_SIZE
    _log(state, f"Project Ideas: starting — {len(jobs)} jobs in {total_batches} batch(es) (with web search).")
    for j in jobs:
        j.setdefault("project_suggestions", "No project suggestions generated.")
    for batch_start in range(0, len(jobs), BATCH_SIZE):
        batch_idx = batch_start // BATCH_SIZE + 1
        batch = jobs[batch_start : batch_start + BATCH_SIZE]
        job_range = f"jobs {batch_start + 1}–{batch_start + len(batch)}"
        _log(state, f"Project Ideas: batch {batch_idx}/{total_batches} — generating project ideas for {job_range} (with web search)...")
        prompt = _batch_projects_prompt(batch, resume, cover)
        text = _rate_limited_gemini(prompt, use_search_grounding=True)
        if text.strip():
            try:
                items = _extract_json_array(text)
                for item in items:
                    idx = item.get("idx")
                    projects = item.get("projects", [])
                    if idx is not None and 0 <= int(idx) < len(batch):
                        batch[int(idx)]["project_suggestions"] = json.dumps(projects) if isinstance(projects, list) else str(projects)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                err_preview = str(e)[:80]
                _log(state, f"Project Ideas: batch {batch_idx}/{total_batches} — could not parse model output ({err_preview}); keeping defaults.")
        _log(state, f"Project Ideas: batch {batch_idx}/{total_batches} — done for {job_range}.")
    _log(state, "Project Ideas: all batches complete.")
    return {"qualifying_jobs": jobs, "_log_phase": 2}


def future_scores_node(state: V3State) -> Dict[str, Any]:
    jobs = state.get("qualifying_jobs") or []
    resume = state.get("resume") or ""
    cover = state.get("cover_letter") or ""
    _log(state, "Predicting future scores...")
    prompt = _batch_future_scores_prompt(jobs, resume, cover)
    text = _rate_limited_gemini(prompt)
    for j in jobs:
        cur = j.get("score", 50)
        j.setdefault("future_score", min(100, cur + 10))
        j.setdefault("improvement_potential", j["future_score"] - cur)
    if text.strip():
        for item in _extract_json_array(text):
            idx = item.get("idx")
            fs = item.get("future_score", 0)
            if idx is not None and 0 <= int(idx) < len(jobs):
                j = jobs[int(idx)]
                j["future_score"] = max(0, min(100, int(fs)))
                j["improvement_potential"] = j["future_score"] - j.get("score", 50)
    update_relevant_jobs(jobs)
    _log(state, f"Future scores done — {len(jobs)} jobs.")
    return {"qualifying_jobs": jobs}


# ---------------------------------------------------------------------------
# Relevance summary: What is working / What is not working (full context)
# ---------------------------------------------------------------------------

RELEVANCE_BATCH_SIZE = 6

def _batch_relevance_summary_prompt(jobs_batch: List[Dict], resume_text: str, cover_letter_text: str) -> str:
    resume = _resume_for_prompt(resume_text or "")
    cover = _cover_for_prompt(cover_letter_text or "")
    cl = f"\nCover letter:\n{cover}\n" if cover else ""
    jobs_block = ""
    for i, job in enumerate(jobs_batch):
        desc = (job.get("description") or "")[:800]
        title = job.get("title", "N/A")
        company = job.get("company", "N/A")
        score = job.get("score", 50)
        jobs_block += f"\n--- JOB {i} ---\nTitle: {title}\nCompany: {company}\nScore: {score}\nDescription:\n{desc}\n"
    return (
        f"You are a hiring manager. For each job, compare the candidate's resume to the role requirements and write a brief assessment.\n\n"
        f"=== JOBS ===\n{jobs_block}\n\n"
        f"=== CANDIDATE RESUME ===\n{resume}\n{cl}\n"
        f"Read the ENTIRE resume including Projects, Activities, and Skills sections.\n\n"
        f"For each job return:\n"
        f"- working: 1 sentence — the strongest match between the candidate's background and this role. Cite a specific experience or skill.\n"
        f"- not_working: 1 sentence — the single most important qualification this role requires that the candidate lacks evidence of. "
        f"Focus on real gaps only (missing domain experience, required skill not demonstrated anywhere, seniority level, certification). "
        f"Do NOT restate the job description. Do NOT flag things the candidate has.\n\n"
        f"Return ONLY a JSON array: [{{\"idx\": 0, \"working\": \"...\", \"not_working\": \"...\"}}, ...]. No markdown."
    )


def relevance_summary_node(state: V3State) -> Dict[str, Any]:
    jobs = state.get("qualifying_jobs") or []
    resume = state.get("resume") or ""
    cover = state.get("cover_letter") or ""
    total_batches = (len(jobs) + RELEVANCE_BATCH_SIZE - 1) // RELEVANCE_BATCH_SIZE
    _log(state, f"Writing relevance summaries — {len(jobs)} jobs in {total_batches} batch(es)...")
    for batch_start in range(0, len(jobs), RELEVANCE_BATCH_SIZE):
        batch = jobs[batch_start : batch_start + RELEVANCE_BATCH_SIZE]
        batch_idx = batch_start // RELEVANCE_BATCH_SIZE + 1
        _log(state, f"Relevance summary: batch {batch_idx}/{total_batches}...")
        prompt = _batch_relevance_summary_prompt(batch, resume, cover)
        text = _rate_limited_gemini(prompt)
        if not text.strip():
            continue
        for item in _extract_json_array(text):
            idx = item.get("idx")
            working = (item.get("working") or "").strip()
            not_working = (item.get("not_working") or "").strip()
            if idx is not None and 0 <= int(idx) < len(batch):
                j = batch[int(idx)]
                parts = []
                if working:
                    parts.append(f"**What is working:** {working}")
                if not_working:
                    parts.append(f"**What is not working:** {not_working}")
                j["brief_relevance_summary"] = "\n\n".join(parts) if parts else ""
    _log(state, f"Relevance summaries done for {len(jobs)} jobs.")
    return {"qualifying_jobs": jobs}


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_v3_workflow():
    workflow = StateGraph(V3State)

    workflow.add_node("decide_titles", decide_titles_node)
    workflow.add_node("phase1_agent", phase1_agent_node)
    workflow.add_node("phase1_tools", phase1_tool_node)
    workflow.add_node("score_batch", score_batch_node)
    workflow.add_node("resume_modifier_agent", resume_modifier_agent_node)
    workflow.add_node("project_proposer", project_proposer_node)
    workflow.add_node("future_scores", future_scores_node)
    workflow.add_node("relevance_summary", relevance_summary_node)

    workflow.set_entry_point("decide_titles")
    workflow.add_edge("decide_titles", "phase1_agent")
    workflow.add_conditional_edges(
        "phase1_agent",
        phase1_route,
        {"phase1_tools": "phase1_tools", "resume_modifier_agent": "resume_modifier_agent", "phase1_agent": "phase1_agent"},
    )
    workflow.add_edge("phase1_tools", "score_batch")
    workflow.add_edge("score_batch", "phase1_agent")

    workflow.add_edge("resume_modifier_agent", "project_proposer")

    workflow.add_edge("project_proposer", "future_scores")
    workflow.add_edge("future_scores", "relevance_summary")
    workflow.add_edge("relevance_summary", END)

    return workflow.compile()
