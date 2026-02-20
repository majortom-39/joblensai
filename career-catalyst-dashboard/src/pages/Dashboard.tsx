import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LayoutGrid, List, Search, Loader2, Inbox } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { JobCard } from "@/components/JobCard";
import { JobTable } from "@/components/JobTable";
import { ProjectBriefModal } from "@/components/ProjectBriefModal";
import { ProjectSuggestion } from "@/data/mockData";
import { useJobs } from "@/hooks/useJobs";

type SortMode = "recent" | "relevant";

export default function Dashboard() {
  const navigate = useNavigate();
  const { jobs, loading, toggleSave, applyJob } = useJobs();
  const [view, setView] = useState<"grid" | "table">("grid");
  const [search, setSearch] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("relevant");
  const [selectedProject, setSelectedProject] = useState<ProjectSuggestion | null>(null);

  const filtered = jobs
    .filter(
      (j) =>
        j.title.toLowerCase().includes(search.toLowerCase()) ||
        j.company.toLowerCase().includes(search.toLowerCase())
    )
    .slice()
    .sort((a, b) => {
      if (sortMode === "recent") {
        const pa = a.posted_at || "";
        const pb = b.posted_at || "";
        if (!pa && !pb) return 0;
        if (!pa) return 1;
        if (!pb) return -1;
        return pa > pb ? -1 : pa < pb ? 1 : 0;
      }
      return (b.relevanceScore ?? 0) - (a.relevanceScore ?? 0);
    });

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-3 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" />
        <p className="text-sm">Loading your results…</p>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4 text-muted-foreground">
        <Inbox className="h-12 w-12 opacity-40" />
        <div className="text-center">
          <p className="font-medium text-foreground">No results yet</p>
          <p className="text-sm mt-1">Upload your resume and run the agents to see matched jobs here.</p>
        </div>
        <button
          onClick={() => navigate("/")}
          className="text-sm text-primary underline underline-offset-4 hover:opacity-80 transition-opacity"
        >
          Go to Upload & Analyze
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Job Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {filtered.length} jobs matched your profile — sorted by {sortMode === "recent" ? "most recent" : "relevance"}
        </p>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex border rounded-lg overflow-hidden">
          <Button
            variant={sortMode === "recent" ? "default" : "ghost"}
            size="sm"
            className="rounded-none"
            onClick={() => setSortMode("recent")}
          >
            Recent
          </Button>
          <Button
            variant={sortMode === "relevant" ? "default" : "ghost"}
            size="sm"
            className="rounded-none"
            onClick={() => setSortMode("relevant")}
          >
            Relevant
          </Button>
        </div>
        <div className="flex border rounded-lg overflow-hidden">
          <Button
            variant={view === "grid" ? "default" : "ghost"}
            size="sm"
            className="rounded-none"
            onClick={() => setView("grid")}
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
          <Button
            variant={view === "table" ? "default" : "ghost"}
            size="sm"
            className="rounded-none"
            onClick={() => setView("table")}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Job listings */}
      {view === "grid" ? (
        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((job) => (
            <div key={job.id}>
              <JobCard
                job={job}
                onSave={toggleSave}
                onApply={applyJob}
                onViewProject={setSelectedProject}
              />
            </div>
          ))}
        </div>
      ) : (
        <JobTable
          jobs={filtered}
          onSave={toggleSave}
          onApply={applyJob}
          onSelect={() => {}}
        />
      )}

      {/* Project brief modal */}
      <ProjectBriefModal
        project={selectedProject}
        onClose={() => setSelectedProject(null)}
      />
    </div>
  );
}
