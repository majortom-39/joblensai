import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Loader2, Circle, AlertCircle } from "lucide-react";
import { AgentStep } from "@/data/mockData";

const statusConfig = {
  pending: { icon: Circle, color: "text-muted-foreground", bg: "bg-muted", line: "bg-border" },
  running: { icon: Loader2, color: "text-primary", bg: "bg-primary/10", line: "bg-primary/40" },
  completed: { icon: CheckCircle2, color: "text-success", bg: "bg-success/10", line: "bg-success/40" },
  error: { icon: AlertCircle, color: "text-destructive", bg: "bg-destructive/10", line: "bg-destructive/40" },
};

function StepLogs({ logs }: { logs: string[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="mt-2 max-h-36 overflow-y-auto rounded-md bg-muted/40 border px-3 py-2 font-mono text-[11px] space-y-0.5">
      {logs.map((msg, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.15 }}
          className="flex gap-2 leading-relaxed"
        >
          <span className="text-muted-foreground/40 select-none shrink-0">
            {String(i + 1).padStart(2, "0")}
          </span>
          <span className={i === logs.length - 1 ? "text-foreground font-medium" : "text-muted-foreground"}>
            {msg}
          </span>
        </motion.div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

export function AgentTimeline({ steps }: { steps: AgentStep[] }) {
  return (
    <div className="space-y-0">
      {steps.map((step, i) => {
        const config = statusConfig[step.status];
        const Icon = config.icon;
        const isLast = i === steps.length - 1;
        const hasLogs = step.logs && step.logs.length > 0;
        const showLogs = hasLogs && (step.status === "running" || step.status === "completed" || step.status === "error");

        return (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="flex gap-4"
          >
            {/* Timeline line + icon */}
            <div className="flex flex-col items-center">
              <div className={`h-9 w-9 rounded-full ${config.bg} flex items-center justify-center shrink-0`}>
                <Icon
                  className={`h-4 w-4 ${config.color} ${step.status === "running" ? "animate-spin" : ""}`}
                />
              </div>
              {!isLast && (
                <div className={`w-0.5 flex-1 min-h-[24px] ${config.line} transition-colors duration-500`} />
              )}
            </div>

            {/* Content */}
            <div className="pb-6 pt-1.5 flex-1 min-w-0">
              <p className={`text-sm font-semibold ${step.status === "running" ? "text-primary" : "text-foreground"}`}>
                {step.name}
                {step.status === "running" && (
                  <span className="relative inline-flex ml-2 h-1.5 w-1.5 align-middle">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary" />
                  </span>
                )}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
              {step.duration && (
                <p className="text-xs text-muted-foreground/60 mt-1">Completed in {step.duration}</p>
              )}
              {showLogs && <StepLogs logs={step.logs!} />}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
