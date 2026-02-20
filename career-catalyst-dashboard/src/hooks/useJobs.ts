/**
 * useJobs — shared hook for all job pages.
 *
 * - Loads real jobs from the API once (keyed by job_id in localStorage)
 * - Persists saved/applied flags in localStorage so they survive page navigation
 * - All three pages (Dashboard, SavedJobs, AppliedJobs) use the same source
 */

import { useState, useEffect, useCallback } from "react";
import { JobListing } from "@/data/mockData";
import { getResults } from "@/services/api";

const JOBS_CACHE_KEY = "joblens_jobs";
const FLAGS_KEY = "joblens_flags"; // {[id]: {saved, applied}}

type Flags = Record<string, { saved: boolean; applied: boolean }>;

function loadFlags(): Flags {
  try {
    return JSON.parse(localStorage.getItem(FLAGS_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveFlags(flags: Flags) {
  localStorage.setItem(FLAGS_KEY, JSON.stringify(flags));
}

function applyFlags(jobs: JobListing[], flags: Flags): JobListing[] {
  return jobs.map((j) => ({
    ...j,
    saved: flags[j.id]?.saved ?? j.saved ?? false,
    applied: flags[j.id]?.applied ?? j.applied ?? false,
  }));
}

export function useJobs() {
  const [jobs, setJobs] = useState<JobListing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const jobId = localStorage.getItem("joblens_job_id");

    if (!jobId) {
      setLoading(false);
      return;
    }

    // Use cached jobs if available (avoids re-fetching on every page visit)
    const cached = localStorage.getItem(JOBS_CACHE_KEY);
    if (cached) {
      try {
        const parsed: JobListing[] = JSON.parse(cached);
        const flags = loadFlags();
        setJobs(applyFlags(parsed, flags));
        setLoading(false);
        return;
      } catch {
        localStorage.removeItem(JOBS_CACHE_KEY);
      }
    }

    getResults(jobId)
      .then((realJobs) => {
        localStorage.setItem(JOBS_CACHE_KEY, JSON.stringify(realJobs));
        const flags = loadFlags();
        setJobs(applyFlags(realJobs, flags));
      })
      .catch((err) => console.warn("[useJobs] Could not load results:", err))
      .finally(() => setLoading(false));
  }, []);

  const toggleSave = useCallback((id: string) => {
    setJobs((prev) => {
      const updated = prev.map((j) =>
        j.id === id ? { ...j, saved: !j.saved } : j
      );
      const flags = loadFlags();
      const job = updated.find((j) => j.id === id);
      if (job) {
        flags[id] = { saved: job.saved ?? false, applied: job.applied ?? false };
        saveFlags(flags);
      }
      return updated;
    });
  }, []);

  const applyJob = useCallback((id: string) => {
    setJobs((prev) => {
      const updated = prev.map((j) =>
        j.id === id ? { ...j, applied: true } : j
      );
      const flags = loadFlags();
      const job = updated.find((j) => j.id === id);
      if (job) {
        flags[id] = { saved: job.saved ?? false, applied: true };
        saveFlags(flags);
      }
      return updated;
    });
  }, []);

  return { jobs, loading, toggleSave, applyJob };
}
