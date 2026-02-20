import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckSquare, Loader2 } from "lucide-react";
import { JobCard } from "@/components/JobCard";
import { ProjectBriefModal } from "@/components/ProjectBriefModal";
import { ProjectSuggestion } from "@/data/mockData";
import { useJobs } from "@/hooks/useJobs";

export default function AppliedJobs() {
  const navigate = useNavigate();
  const { jobs, loading, toggleSave, applyJob } = useJobs();
  const [selectedProject, setSelectedProject] = useState<ProjectSuggestion | null>(null);

  const applied = jobs.filter((j) => j.applied);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-3 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
        <p className="text-sm">Loading applied jobs…</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <CheckSquare className="h-5 w-5 text-success" /> Applied Jobs
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {applied.length} application{applied.length !== 1 ? "s" : ""} submitted
        </p>
      </div>

      {applied.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CheckSquare className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>No applications yet.</p>
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
              Apply to jobs from the dashboard
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4">
          {applied.map((job) => (
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
