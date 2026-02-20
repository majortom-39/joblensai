import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { MapPin, Clock, Bookmark, BookmarkCheck, ExternalLink, ChevronDown, ChevronUp, Lightbulb, Wrench, TrendingUp, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { JobListing, ProjectSuggestion } from "@/data/mockData";

interface Props {
  job: JobListing;
  onSave: (id: string) => void;
  onApply: (id: string) => void;
  onViewProject: (project: ProjectSuggestion) => void;
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 85 ? "bg-success/10 text-success" : score >= 70 ? "bg-warning/10 text-warning" : "bg-muted text-muted-foreground";
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold ${color}`}>
      <TrendingUp className="h-3 w-3" />
      {score}%
    </div>
  );
}

/** Parse "**What is working:** ... **What is not working:** ..." into structured parts for nice formatting. */
function parseRelevanceSummary(text: string): { working: string | null; notWorking: string | null } {
  if (!text || !text.trim()) return { working: null, notWorking: null };
  const raw = text.trim();
  const notWorkingMarker = "**What is not working:**";
  const workingMarker = "**What is working:**";
  const idxNot = raw.indexOf(notWorkingMarker);
  const idxWorking = raw.indexOf(workingMarker);
  if (idxWorking === -1 && idxNot === -1) return { working: null, notWorking: null };
  let working: string | null = null;
  let notWorking: string | null = null;
  if (idxNot !== -1) {
    notWorking = raw.slice(idxNot + notWorkingMarker.length).trim();
    if (idxWorking !== -1 && idxWorking < idxNot) {
      working = raw.slice(idxWorking + workingMarker.length, idxNot).trim();
    }
  }
  if (idxWorking !== -1 && working === null && idxNot === -1) {
    working = raw.slice(idxWorking + workingMarker.length).trim();
  }
  if (idxWorking !== -1 && working === null && idxNot !== -1 && idxWorking < idxNot) {
    working = raw.slice(idxWorking + workingMarker.length, idxNot).trim();
  }
  return { working, notWorking };
}

const JOB_CARD_FIXED_HEIGHT = 580;
const OVERALL_DEFAULT_HEIGHT = 90;
const RESUME_DEFAULT_HEIGHT = 280;
const PROJECTS_HEADER_HEIGHT = 48;

export function JobCard({ job, onSave, onApply, onViewProject }: Props) {
  const [overallExpanded, setOverallExpanded] = useState(false);
  const [suggestionsExpanded, setSuggestionsExpanded] = useState(false);
  const [projectsExpanded, setProjectsExpanded] = useState(false);
  const [overallHasOverflow, setOverallHasOverflow] = useState(false);
  const [suggestionsHasOverflow, setSuggestionsHasOverflow] = useState(false);
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);

  const overallContentRef = useRef<HTMLDivElement>(null);
  const suggestionsContentRef = useRef<HTMLDivElement>(null);

  const sectionedSuggestions = job.bulletSuggestionsBySection ?? [];
  const flatSuggestions = job.bulletSuggestions ?? [];
  const hasSectioned = sectionedSuggestions.length > 0;
  const hasFlat = !hasSectioned && flatSuggestions.length > 0;
  const suggestionCount = hasSectioned ? sectionedSuggestions.length : flatSuggestions.length;
  const relevanceText = job.relevanceSummary ?? job.description ?? "";
  const relevanceParsed = parseRelevanceSummary(relevanceText);
  const hasProjects = job.suggestedProjects && job.suggestedProjects.length > 0;
  const anyExpanded = overallExpanded || suggestionsExpanded || projectsExpanded;

  useEffect(() => {
    const check = (ref: React.RefObject<HTMLDivElement | null>, set: (v: boolean) => void) => {
      if (!ref.current) return;
      set(ref.current.scrollHeight > ref.current.clientHeight);
    };
    const id = setTimeout(() => {
      if (!overallExpanded) check(overallContentRef, setOverallHasOverflow);
      if (!suggestionsExpanded) check(suggestionsContentRef, setSuggestionsHasOverflow);
    }, 0);
    return () => clearTimeout(id);
  }, [job, overallExpanded, suggestionsExpanded]);

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <Card
        className="overflow-hidden hover:shadow-md transition-shadow flex flex-col transition-[height] duration-200"
        style={{
          minHeight: JOB_CARD_FIXED_HEIGHT,
          height: anyExpanded ? "auto" : JOB_CARD_FIXED_HEIGHT,
        }}
      >
        <CardContent className="p-5 flex flex-col flex-1 min-h-0">
          {/* Top row — fixed */}
          <div className="flex items-start justify-between gap-3 shrink-0">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-card-foreground">{job.title}</h3>
                <ScoreBadge score={job.relevanceScore} />
              </div>
              <p className="text-sm font-medium text-primary mt-0.5">{job.company}</p>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location}</span>
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{job.postedDate}</span>
              </div>
              <div className="flex gap-1.5 mt-2">
                <Badge variant="secondary" className="text-xs">{job.type}</Badge>
                <Badge variant="outline" className="text-xs">{job.salary}</Badge>
              </div>
            </div>

            <div className="flex gap-1.5 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onSave(job.id)}
                className={job.saved ? "text-primary" : "text-muted-foreground"}
              >
                {job.saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
              </Button>
              {job.applied ? (
                <Button
                  size="sm"
                  disabled
                  className="bg-success hover:bg-success text-success-foreground"
                >
                  Applied
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    if (job.url) window.open(job.url, "_blank", "noopener,noreferrer");
                    setApplyDialogOpen(true);
                  }}
                >
                  Apply
                  <ExternalLink className="h-3 w-3 ml-1" />
                </Button>
              )}
            </div>
          </div>

          {/* Overall — smaller fixed height by default; open; chevron when content overflows */}
          <div className="shrink-0 mt-3">
            <div
              className="p-3 rounded-lg bg-primary/5 border border-primary/10 overflow-hidden flex flex-col transition-[max-height] duration-200"
              style={{ maxHeight: overallExpanded ? "none" : OVERALL_DEFAULT_HEIGHT }}
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold text-primary shrink-0">
                <FileText className="h-3.5 w-3.5 shrink-0" />
                <span>Overall</span>
                {(overallHasOverflow || overallExpanded) && (
                  <button
                    type="button"
                    onClick={() => setOverallExpanded(!overallExpanded)}
                    className="ml-auto shrink-0 p-0.5 hover:opacity-80 transition-opacity"
                    aria-label={overallExpanded ? "Show less" : "Show more"}
                  >
                    {overallExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>
                )}
              </div>
              <div
                ref={overallContentRef}
                className="overflow-hidden text-sm text-muted-foreground mt-1.5 min-h-0 space-y-2"
                style={overallExpanded ? undefined : { maxHeight: OVERALL_DEFAULT_HEIGHT - 42 }}
              >
                {relevanceParsed.working !== null || relevanceParsed.notWorking !== null ? (
                  <>
                    {relevanceParsed.working !== null && (
                      <p>
                        <span className="font-semibold text-foreground">What is working:</span>{" "}
                        {relevanceParsed.working}
                      </p>
                    )}
                    {relevanceParsed.notWorking !== null && (
                      <p>
                        <span className="font-semibold text-foreground">What is not working:</span>{" "}
                        {relevanceParsed.notWorking}
                      </p>
                    )}
                  </>
                ) : (
                  <p>{relevanceText || "No summary available."}</p>
                )}
              </div>
            </div>
          </div>

          {/* Resume Enhancement Suggestions — largest default height; secondary color; always reserve space so all cards match */}
          <div className="shrink-0 mt-3">
            <div
              className="p-3 rounded-lg bg-secondary/5 border border-secondary/10 overflow-hidden flex flex-col transition-[max-height] duration-200"
              style={{ maxHeight: suggestionsExpanded ? "none" : RESUME_DEFAULT_HEIGHT }}
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold text-secondary-foreground shrink-0">
                <Lightbulb className="h-3.5 w-3.5 shrink-0" />
                <span>Resume Enhancement Suggestions{suggestionCount > 0 ? ` (${suggestionCount})` : ""}</span>
                {(hasSectioned || hasFlat) && (suggestionsHasOverflow || suggestionsExpanded) && (
                  <button
                    type="button"
                    onClick={() => setSuggestionsExpanded(!suggestionsExpanded)}
                    className="ml-auto shrink-0 p-0.5 hover:opacity-80 transition-opacity"
                    aria-label={suggestionsExpanded ? "Show less" : "Show more"}
                  >
                    {suggestionsExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>
                )}
              </div>
              {(hasSectioned || hasFlat) ? (
                <div
                  ref={suggestionsContentRef}
                  className="overflow-hidden mt-1.5 space-y-2 min-h-0"
                  style={suggestionsExpanded ? undefined : { maxHeight: RESUME_DEFAULT_HEIGHT - 42 }}
                >
                  {hasSectioned && (
                    <ul className="space-y-2">
                      {sectionedSuggestions.map((item, i) => (
                        <li key={i} className="text-xs pl-3 border-l-2 border-secondary/20">
                          <span className="font-medium text-secondary-foreground/90">{item.section}</span>
                          <p className="text-muted-foreground mt-0.5">{item.suggestion}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                  {hasFlat && (
                    <ul className="space-y-1.5">
                      {flatSuggestions.map((s, i) => (
                        <li key={i} className="text-xs text-muted-foreground pl-3 border-l-2 border-secondary/20">
                          {s}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <div className="mt-1.5 text-xs text-muted-foreground min-h-[120px]">No suggestions for this job.</div>
              )}
            </div>
          </div>

          {/* Spacer: pushes Projects to the bottom in default state so no gap at bottom */}
          {!anyExpanded && <div className="flex-1 min-h-0 min-w-0" />}

          {/* Projects — collapsed by default; at the end of card; accent color; always reserve space so all cards match */}
          <div className="shrink-0 mt-3">
            <div
              className="p-3 rounded-lg bg-accent/5 border border-accent/15 overflow-hidden flex flex-col transition-[max-height] duration-200"
              style={{ maxHeight: projectsExpanded && hasProjects ? "none" : PROJECTS_HEADER_HEIGHT }}
            >
              <button
                type="button"
                onClick={() => hasProjects && setProjectsExpanded(!projectsExpanded)}
                className="flex items-center gap-1.5 text-xs font-semibold text-accent hover:text-accent/80 transition-colors text-left w-full disabled:opacity-70"
                disabled={!hasProjects}
              >
                <Wrench className="h-3.5 w-3.5 shrink-0" />
                <span>{hasProjects ? `${job.suggestedProjects!.length} project${job.suggestedProjects!.length > 1 ? "s" : ""} to boost your score` : "Projects to boost your score"}</span>
                {hasProjects && (projectsExpanded ? <ChevronUp className="h-3 w-3 ml-auto shrink-0" /> : <ChevronDown className="h-3 w-3 ml-auto shrink-0" />)}
              </button>
              {projectsExpanded && hasProjects && (
                <div className="mt-2 space-y-2">
                  {job.suggestedProjects!.map((proj) => (
                    <div
                      key={proj.id}
                      className="p-3 rounded-md bg-background/60 border border-accent/10 flex items-center justify-between gap-3 cursor-pointer hover:bg-accent/10 transition-colors"
                      onClick={() => onViewProject(proj)}
                    >
                      <div>
                        <p className="text-sm font-medium text-card-foreground">{proj.title}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">{proj.difficulty}</Badge>
                          <span className="text-[10px] text-muted-foreground">{proj.estimatedTime}</span>
                          <span className="text-[10px] font-bold text-success">+{proj.scoreBoost} pts</span>
                        </div>
                      </div>
                      <ExternalLink className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={applyDialogOpen} onOpenChange={setApplyDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Did you apply to {job.title}?</AlertDialogTitle>
            <AlertDialogDescription>
              Confirm that you applied to the position at <span className="font-medium text-foreground">{job.company}</span> so we can track it for you.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>No, I didn't</AlertDialogCancel>
            <AlertDialogAction onClick={() => onApply(job.id)}>
              Yes, I applied
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </motion.div>
  );
}
