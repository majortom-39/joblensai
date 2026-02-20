import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bookmark, Loader2 } from "lucide-react";
import { JobCard } from "@/components/JobCard";
import { ProjectBriefModal } from "@/components/ProjectBriefModal";
import { ProjectSuggestion } from "@/data/mockData";
import { useJobs } from "@/hooks/useJobs";

export default function SavedJobs() {
  const navigate = useNavigate();
  const { jobs, loading, toggleSave, applyJob } = useJobs();
  const [selectedProject, setSelectedProject] = useState<ProjectSuggestion | null>(null);

  const saved = jobs.filter((j) => j.saved);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-3 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
        <p className="text-sm">Loading saved jobs…</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Bookmark className="h-5 w-5 text-primary" /> Saved Jobs
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {saved.length} job{saved.length !== 1 ? "s" : ""} saved
        </p>
      </div>

      {saved.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Bookmark className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>No saved jobs yet.</p>
          {jobs.length === 0 ? (
            <button
              onClick={() => navigate("/")}
              className="mt-2 text-sm text-primary underline underline-offset-4 hover:opacity-80 transition-opacity"
            >
              Run an analysis first to find jobs
            </button>
          ) : (
            <button
              onClick={() => navigate("/dashboard")}
              className="mt-2 text-sm text-primary underline underline-offset-4 hover:opacity-80 transition-opacity"
            >
              Save jobs from the dashboard
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4">
          {saved.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onSave={toggleSave}
              onApply={applyJob}
              onViewProject={setSelectedProject}
            />
          ))}
        </div>
      )}

      <ProjectBriefModal project={selectedProject} onClose={() => setSelectedProject(null)} />
    </div>
  );
}
