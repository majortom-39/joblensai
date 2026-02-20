export interface JobListing {
  id: string;
  title: string;
  company: string;
  location: string;
  type: string;
  salary: string;
  relevanceScore: number;
  postedDate: string;
  posted_at?: string;
  description: string;
  relevanceSummary?: string | null;
  url?: string;
  source?: string;
  bulletSuggestions?: string[];
  bulletSuggestionsBySection?: { section: string; suggestion: string }[];
  suggestedProjects?: ProjectSuggestion[];
  futureScore?: number;
  improvementPotential?: number;
  saved?: boolean;
  applied?: boolean;
}

export interface ProjectSuggestion {
  id: string;
  title: string;
  difficulty: "Beginner" | "Intermediate" | "Advanced";
  estimatedTime: string;
  scoreBoost: number;
  brief: string;
  explanation: string;
  techStack: string[];
  steps: string[];
}

export interface AgentStep {
  id: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "error";
  duration?: string;
  logs?: string[];
}

export const mockAgentSteps: AgentStep[] = [
  {
    id: "1",
    name: "Job Acquisition Agent",
    description: "AI suggests job titles from resume; scraping and scoring until 10+ jobs with relevancy >= 85",
    status: "pending",
  },
  {
    id: "2",
    name: "Resume Optimizer",
    description: "Generating tailored resume suggestions for each matched job",
    status: "pending",
  },
  {
    id: "3",
    name: "Project Ideas Agent",
    description: "Researching portfolio project ideas and calculating score improvement",
    status: "pending",
  },
];
