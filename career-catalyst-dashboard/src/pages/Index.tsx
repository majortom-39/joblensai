import { useState, useCallback, useRef } from "react";
import { Upload, FileText, Briefcase, Play, RotateCcw, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AgentTimeline } from "@/components/AgentTimeline";
import { mockAgentSteps, AgentStep } from "@/data/mockData";
import { submitAnalysis, pollStatus, type JobType } from "@/services/api";

const POLL_INTERVAL_MS = 3000;

const Index = () => {
  const navigate = useNavigate();

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [coverLetterFile, setCoverLetterFile] = useState<File | null>(null);
  const [jobType, setJobType] = useState<JobType>("full_time");
  const [steps, setSteps] = useState<AgentStep[]>(mockAgentSteps);
  const [isRunning, setIsRunning] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const launchAgents = useCallback(async () => {
    if (!resumeFile) {
      setError("Please upload your resume before launching.");
      return;
    }

    setError(null);
    setIsRunning(true);
    setIsDone(false);
    setSteps(mockAgentSteps.map((s) => ({ ...s, status: "pending" as const })));
    localStorage.removeItem("joblens_jobs");

    let jobId: string;
    try {
      jobId = await submitAnalysis(resumeFile, coverLetterFile, jobType);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis.");
      setIsRunning(false);
      return;
    }

    localStorage.setItem("joblens_job_id", jobId);

    pollRef.current = setInterval(async () => {
      try {
        const status = await pollStatus(jobId);

        setSteps(
          status.steps.map((s) => ({
            id: s.id,
            name: s.name,
            description: s.description,
            status: s.status as AgentStep["status"],
            duration: s.duration ?? undefined,
            logs: s.logs ?? [],
          }))
        );

        if (status.status === "completed") {
          stopPolling();
          setIsRunning(false);
          setIsDone(true);
          setTimeout(() => navigate("/dashboard"), 1200);
        } else if (status.status === "error") {
          stopPolling();
          setIsRunning(false);
          setError(status.error ?? "An error occurred during analysis.");
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const is404 = err && typeof err === "object" && "status" in err && (err as { status: number }).status === 404;
        if (is404 || message.includes("404")) {
          stopPolling();
          setIsRunning(false);
          setError("Job session not found. The server may have restarted — please upload and launch again.");
        } else {
          console.warn("[Poll] Status check failed:", err);
        }
      }
    }, POLL_INTERVAL_MS);
  }, [resumeFile, coverLetterFile, jobType, navigate]);

  const reset = () => {
    stopPolling();
    setSteps(mockAgentSteps);
    setIsRunning(false);
    setIsDone(false);
    setError(null);
    localStorage.removeItem("joblens_job_id");
    localStorage.removeItem("joblens_jobs");
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header + Launch button */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Upload & Analyze</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload your documents and let AI agents find your best matches
          </p>
        </div>
        <div className="flex items-center gap-3">
          {(isDone || error) && (
            <Button variant="outline" onClick={reset}>
              <RotateCcw className="h-4 w-4 mr-1.5" /> Reset
            </Button>
          )}
          <Button
            onClick={launchAgents}
            disabled={isRunning || !resumeFile}
            size="lg"
            className="shadow-lg shadow-primary/20"
          >
            <Play className="h-4 w-4 mr-1.5" />
            {isRunning ? "Agents Running..." : "Launch Agents"}
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </motion.div>
      )}

      {/* Upload section */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" /> Resume
            </CardTitle>
          </CardHeader>
          <CardContent>
            <label className="flex flex-col items-center justify-center h-28 border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 hover:border-primary/30 transition-colors">
              <Upload className="h-6 w-6 text-muted-foreground mb-1.5" />
              <span className="text-xs text-muted-foreground text-center px-2">
                {resumeFile ? resumeFile.name : "Click to upload PDF, DOCX"}
              </span>
              <input
                type="file"
                className="hidden"
                accept=".pdf,.docx,.doc,.txt"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              />
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" /> Cover Letter{" "}
              <span className="text-xs font-normal text-muted-foreground">(optional)</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <label className="flex flex-col items-center justify-center h-28 border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 hover:border-primary/30 transition-colors">
              <Upload className="h-6 w-6 text-muted-foreground mb-1.5" />
              <span className="text-xs text-muted-foreground text-center px-2">
                {coverLetterFile ? coverLetterFile.name : "Click to upload PDF, DOCX"}
              </span>
              <input
                type="file"
                className="hidden"
                accept=".pdf,.docx,.doc,.txt"
                onChange={(e) => setCoverLetterFile(e.target.files?.[0] || null)}
              />
            </label>
          </CardContent>
        </Card>
      </div>

      {/* Job type: Full-time / Internship / Both */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-primary" /> Job Type
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {(["full_time", "internship", "both"] as const).map((value) => (
              <Button
                key={value}
                variant={jobType === value ? "default" : "outline"}
                size="sm"
                onClick={() => !isRunning && setJobType(value)}
                disabled={isRunning}
              >
                {value === "full_time" ? "Full-time" : value === "internship" ? "Internship" : "Both"}
              </Button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            AI will suggest job titles that match this type from your resume.
          </p>
        </CardContent>
      </Card>

      {/* Job titles — AI suggested */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-primary" /> Job Titles
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Job titles will be suggested by AI from your resume and cover letter.
          </p>
        </CardContent>
      </Card>

      {/* Agent timeline */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            Agent Activity
            <Badge variant="secondary" className="text-xs font-normal">
              LangGraph Agentic
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <AgentTimeline steps={steps} />
        </CardContent>
      </Card>

    </div>
  );
};

export default Index;
