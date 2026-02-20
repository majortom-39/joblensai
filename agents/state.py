"""
Shared State Definition
Single source of truth for the JobSearchState TypedDict used by all agents and main.py.
V3State for the agentic LangGraph V3 workflow.
"""

from typing import TypedDict, List, Dict, Callable, Optional, Any


class JobSearchState(TypedDict):
    # User inputs
    resume: str
    cover_letter: str
    desired_titles: List[str]

    # Agent 1 output
    raw_jobs: List[Dict]

    # Agent 2 outputs
    scored_jobs: List[Dict]
    optimization_suggestions: Dict

    # Live logging callback (set by api.py, optional)
    _log: Optional[Callable[[str], None]]


def emit_log(state: JobSearchState, message: str):
    """Emit a log entry to the frontend if a callback is available."""
    fn = state.get("_log")
    if fn:
        fn(message)


# ---------------------------------------------------------------------------
# V3 Agentic workflow state (LangGraph)
# qualifying_jobs: list of dicts with title, company, location, description, url,
#   score, resume_suggestions, project_suggestions, future_score, improvement_potential
# seen_urls: list (JSON-serializable; convert to set in nodes when needed)
# ---------------------------------------------------------------------------

class V3State(TypedDict, total=False):
    resume: str
    cover_letter: str
    job_type: str
    suggested_titles: List[str]
    qualifying_jobs: List[Dict[str, Any]]
    seen_urls: List[str]
    current_batch: List[Dict[str, Any]]
    phase1_last_tool_call: Optional[Dict[str, Any]]
    last_scrape_result_count: int
    last_qualifying_added_count: int
    last_tried_title: str
    last_tried_page: int
    phase1_tried_pairs: List[Dict[str, Any]]  # [{"title": str, "page": int}, ...] already scraped
    phase1_rounds: int
    phase2_rounds: int
    _log: Optional[Callable[[str], None]]
    _log_phase: int
