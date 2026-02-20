"""
Job Scraper Tool
Purpose: Extract structured job listings from LinkedIn
Uses: JobSpy — free open-source scraper, no API key required
Input: List of job titles, max jobs to return, pagination offset, sort mode
Output: List of jobs with title, company, location, description, url, salary, source
"""

import sys
import os
from typing import Dict, List, Literal, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobspy import scrape_jobs as _jobspy_scrape


# ---------------------------------------------------------------------------
# Salary formatter
# ---------------------------------------------------------------------------

def _format_salary(row) -> str:
    """Convert JobSpy min/max salary fields to a readable string."""
    min_a = row.get("min_amount")
    max_a = row.get("max_amount")
    currency = row.get("currency") or "USD"
    try:
        if min_a and max_a:
            return f"{currency} {int(min_a):,} \u2013 {int(max_a):,}"
        if min_a:
            return f"{currency} {int(min_a):,}+"
    except (ValueError, TypeError):
        pass
    return ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_jobs(
    job_titles: Optional[List[str]] = None,
    max_jobs: int = 5,
    start_offset: int = 0,
    sort_by: Literal["recent", "relevant"] = "recent",
    keywords: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Scrape LinkedIn job listings using JobSpy (no API key required).

    Args:
        job_titles:   Job titles to search for (e.g. ["Product Manager", "UX Designer"])
        max_jobs:     Maximum number of jobs to return (default: 5)
        start_offset: Result offset for pagination (0 = first page, 5 = next 5, etc.)
        sort_by:      "recent" — tight 3-day window; "relevant" — wider 7-day window
        keywords:     Extra keywords appended to search term (used in "relevant" mode)

    Returns:
        List of dicts: {title, company, location, description, salary, url, source}
    """
    titles = (job_titles or ["Software Engineer"])[:3]

    search_term = " OR ".join(f'"{t}"' for t in titles)

    if sort_by == "relevant" and keywords:
        kw_str = " ".join(keywords[:5])
        search_term = f"({search_term}) {kw_str}"

    hours_old = 72 if sort_by == "recent" else 168

    print(f"[SCRAPER] JobSpy LinkedIn search: {search_term} | mode={sort_by} hours_old={hours_old} (offset={start_offset})", flush=True)

    try:
        df = _jobspy_scrape(
            site_name=["linkedin"],
            search_term=search_term,
            location="United States",
            results_wanted=max_jobs + start_offset,
            hours_old=hours_old,
            linkedin_fetch_description=True,
            offset=start_offset,
            verbose=0,
        )
    except Exception as e:
        print(f"[SCRAPER] JobSpy error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return []

    if df is None or df.empty:
        print("[SCRAPER] No results returned by JobSpy", flush=True)
        return []

    # Slice the requested page: rows [start_offset : start_offset+max_jobs]
    slice_df = df.iloc[start_offset : start_offset + max_jobs] if start_offset > 0 else df.head(max_jobs)
    jobs: List[Dict] = []
    for _, row in slice_df.iterrows():
        desc = str(row.get("description") or "")

        city  = str(row.get("city")  or "").strip()
        state = str(row.get("state") or "").strip()
        location = f"{city}, {state}".strip(", ") if city or state else str(row.get("location") or "")

        posted_at = ""
        raw_date = row.get("date_posted") or row.get("DATE_POSTED")
        if raw_date is not None:
            try:
                posted_at = raw_date.isoformat() if hasattr(raw_date, "isoformat") else (raw_date.strftime("%Y-%m-%dT%H:%M:%S") if hasattr(raw_date, "strftime") else str(raw_date))
            except Exception:
                posted_at = str(raw_date)

        posted_display = None
        for key in ("posted_ago", "posted_display", "posted"):
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                posted_display = val.strip()
                break

        jobs.append({
            "title":       row.get("title"),
            "company":     row.get("company"),
            "location":    location,
            "description": desc[:2000] if desc else None,
            "salary":      _format_salary(row),
            "url":         row.get("job_url"),
            "source":      "linkedin",
            "posted_at":   posted_at or None,
            "posted_display": posted_display,
        })
        print(f"[SCRAPER] ({len(jobs)}/{max_jobs}) {row.get('title')} @ {row.get('company')}", flush=True)

    print(f"[SCRAPER] Total extracted: {len(jobs)} jobs", flush=True)
    return jobs
