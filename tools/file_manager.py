"""
File Manager Tool
Purpose: Read/write to markdown and JSON data files
Functions:
- save_keywords() → writes to keywords.md
- save_jobs() → writes to jobs.json
- load_jobs() → reads from jobs.json
- update_relevant_jobs() → writes formatted output to relevantjobs.md
"""

import json
from typing import List, Dict, Optional
from pathlib import Path


DATA_DIR = Path("data")


def ensure_data_dir():
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(exist_ok=True)


def save_keywords(keywords: List[str]) -> None:
    """
    Save extracted keywords to keywords.md.
    
    Args:
        keywords: List of keyword strings
    """
    ensure_data_dir()
    
    keywords_file = DATA_DIR / "keywords.md"
    
    content = "# Extracted Keywords\n\n"
    content += "## Skills and Keywords\n\n"
    for idx, keyword in enumerate(keywords, 1):
        content += f"{idx}. {keyword}\n"
    
    keywords_file.write_text(content, encoding="utf-8")
    print(f"[FILE_MANAGER] Saved {len(keywords)} keywords to {keywords_file}")


def save_jobs(jobs: List[Dict]) -> None:
    """
    Save scraped jobs to jobs.json.
    
    Args:
        jobs: List of job dictionaries
    """
    ensure_data_dir()
    
    jobs_file = DATA_DIR / "jobs.json"
    
    with open(jobs_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    
    print(f"[FILE_MANAGER] Saved {len(jobs)} jobs to {jobs_file}")


def load_jobs() -> List[Dict]:
    """
    Load jobs from jobs.json.
    
    Returns:
        List of job dictionaries, or empty list if file doesn't exist
    """
    jobs_file = DATA_DIR / "jobs.json"
    
    if not jobs_file.exists():
        print(f"[FILE_MANAGER] {jobs_file} does not exist, returning empty list")
        return []
    
    try:
        with open(jobs_file, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        print(f"[FILE_MANAGER] Loaded {len(jobs)} jobs from {jobs_file}")
        return jobs
    except Exception as e:
        print(f"[FILE_MANAGER] Error loading jobs: {e}")
        return []


def update_relevant_jobs(jobs_with_scores: List[Dict]) -> None:
    """
    Write formatted output with scores and suggestions to relevantjobs.md.
    
    Args:
        jobs_with_scores: List of job dictionaries with score and recommendation fields:
            - title, company, location, url
            - score: Match score (0-100)
            - resume_suggestions: List of resume improvement suggestions
            - project_suggestions: List of project ideas
    """
    ensure_data_dir()
    
    relevant_jobs_file = DATA_DIR / "relevantjobs.md"
    
    content = "# Relevant Jobs with Scores and Recommendations\n\n"
    content += f"Total jobs analyzed: {len(jobs_with_scores)}\n\n"
    content += "---\n\n"

    # Jobs arrive pre-sorted by improvement_potential from recalculate_scores_node.
    # Fall back to sorting by score if improvement_potential is absent.
    sorted_jobs = sorted(
        jobs_with_scores,
        key=lambda x: x.get("improvement_potential", x.get("score", 0)),
        reverse=True
    )

    for idx, job in enumerate(sorted_jobs, 1):
        content += f"## {idx}. {job.get('title', 'N/A')}\n\n"
        content += f"**Company:** {job.get('company', 'N/A')}\n\n"
        content += f"**Location:** {job.get('location', 'N/A')}\n\n"
        content += f"**Match Score:** {job.get('score', 0)}/100\n\n"

        if job.get("future_score") is not None:
            content += f"**Future Score (after changes):** {job['future_score']}/100\n\n"
        if job.get("improvement_potential") is not None:
            content += f"**Improvement Potential:** +{job['improvement_potential']} points\n\n"

        content += f"**URL:** {job.get('url', 'N/A')}\n\n"

        # Resume suggestions (may be a string or a list)
        resume_suggestions = job.get("resume_suggestions")
        if resume_suggestions:
            content += "### Resume Suggestions:\n\n"
            if isinstance(resume_suggestions, list):
                for suggestion in resume_suggestions:
                    content += f"- {suggestion}\n"
                content += "\n"
            else:
                content += f"{resume_suggestions}\n\n"

        # Project suggestions (may be a string or a list)
        project_suggestions = job.get("project_suggestions")
        if project_suggestions:
            content += "### Project Suggestions:\n\n"
            if isinstance(project_suggestions, list):
                for project in project_suggestions:
                    content += f"- {project}\n"
                content += "\n"
            else:
                content += f"{project_suggestions}\n\n"

        content += "---\n\n"
    
    relevant_jobs_file.write_text(content, encoding="utf-8")
    print(f"[FILE_MANAGER] Saved {len(jobs_with_scores)} scored jobs to {relevant_jobs_file}")


