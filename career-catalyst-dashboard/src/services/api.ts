import { AgentStep, JobListing } from "@/data/mockData";

const BASE =
  typeof import.meta !== "undefined" &&
  import.meta.env?.DEV
    ? (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001")
    : "/api";

export interface StatusResponse {
  status: "running" | "completed" | "error";
  steps: AgentStep[];
  error?: string | null;
}

export interface ResultsResponse {
  jobs: JobListing[];
}

export type JobType = "full_time" | "internship" | "both";

/**
 * POST /api/analyze
 * Uploads resume + optional cover letter.
 * Returns a job_id to poll with.
 */
export async function submitAnalysis(
  resumeFile: File,
  coverLetterFile: File | null,
  jobType: JobType = "full_time"
): Promise<string> {
  const form = new FormData();
  form.append("resume", resumeFile);
  if (coverLetterFile) {
    form.append("cover_letter", coverLetterFile);
  }
  form.append("job_titles", JSON.stringify([]));
  form.append("job_type", jobType);

  const url = `${BASE}/analyze`;
  const res = await fetch(url, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to start analysis: ${text}`);
  }

  const data = await res.json();
  return data.job_id as string;
}

/**
 * GET /api/status/{job_id}
 * Returns current workflow status and agent step statuses.
 */
export async function pollStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`${BASE}/status/${jobId}`);
  if (res.status === 404) {
    const e = new Error("Job not found (404). The server may have restarted — please try again.") as Error & { status?: number };
    e.status = 404;
    throw e;
  }
  if (!res.ok) {
    throw new Error(`Status check failed: ${res.status}`);
  }
  return res.json();
}

/**
 * GET /api/results/{job_id}
 * Returns the final mapped job listings.
 */
export async function getResults(jobId: string): Promise<JobListing[]> {
  const res = await fetch(`${BASE}/results/${jobId}`);
  if (!res.ok) {
    throw new Error(`Results fetch failed: ${res.status}`);
  }
  const data: ResultsResponse = await res.json();
  return data.jobs;
}
