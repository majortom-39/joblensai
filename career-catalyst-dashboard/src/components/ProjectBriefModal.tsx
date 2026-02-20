import { X, Download, FileText, File } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProjectSuggestion } from "@/data/mockData";

interface Props {
  project: ProjectSuggestion | null;
  onClose: () => void;
}

export function ProjectBriefModal({ project, onClose }: Props) {
  if (!project) return null;

  const downloadAsText = (format: "pdf" | "docx") => {
    // Mock download - in real app this would generate actual PDF/DOCX
    const content = `
PROJECT BRIEF: ${project.title}
${"=".repeat(40)}

Difficulty: ${project.difficulty}
Estimated Time: ${project.estimatedTime}
Score Boost: +${project.scoreBoost} points

BRIEF
${project.brief}

WHY THIS PROJECT?
${project.explanation}

TECH STACK
${project.techStack.join(", ")}

STEPS
${project.steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}
    `.trim();

    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${project.title.replace(/\s+/g, "-").toLowerCase()}-brief.${format === "pdf" ? "pdf" : "docx"}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-foreground/20 backdrop-blur-sm"
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ type: "spring", duration: 0.4 }}
          onClick={(e) => e.stopPropagation()}
          className="relative z-10 w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-xl border bg-card shadow-2xl"
        >
          {/* Header */}
          <div className="sticky top-0 z-10 bg-card border-b px-5 py-4 flex items-start justify-between">
            <div>
              <h3 className="font-bold text-lg text-card-foreground">{project.title}</h3>
              <div className="flex items-center gap-2 mt-1.5">
                <Badge variant="secondary" className="text-xs">{project.difficulty}</Badge>
                <span className="text-xs text-muted-foreground">{project.estimatedTime}</span>
                <Badge className="text-xs bg-success/10 text-success border-0 hover:bg-success/20">
                  +{project.scoreBoost} pts
                </Badge>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0 -mt-1 -mr-1">
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Body */}
          <div className="px-5 py-4 space-y-5">
            <div>
              <h4 className="text-sm font-semibold text-card-foreground mb-1.5">Project Brief</h4>
              <p className="text-sm text-muted-foreground leading-relaxed">{project.brief}</p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-card-foreground mb-1.5">Why This Project?</h4>
              <p className="text-sm text-muted-foreground leading-relaxed">{project.explanation}</p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-card-foreground mb-1.5">Tech Stack</h4>
              <div className="flex flex-wrap gap-1.5">
                {project.techStack.map((tech) => (
                  <Badge key={tech} variant="outline" className="text-xs">{tech}</Badge>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-card-foreground mb-1.5">Steps</h4>
              <ol className="space-y-1.5">
                {project.steps.map((step, i) => (
                  <li key={i} className="flex gap-2.5 text-sm text-muted-foreground">
                    <span className="text-primary font-semibold text-xs mt-0.5 shrink-0 w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-card border-t px-5 py-3 flex gap-2">
            <Button variant="outline" size="sm" onClick={() => downloadAsText("pdf")} className="flex-1">
              <FileText className="h-3.5 w-3.5 mr-1.5" />
              Download PDF
            </Button>
            <Button variant="outline" size="sm" onClick={() => downloadAsText("docx")} className="flex-1">
              <File className="h-3.5 w-3.5 mr-1.5" />
              Download Word
            </Button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
