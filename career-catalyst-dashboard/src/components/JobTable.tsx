import { Bookmark, BookmarkCheck, ExternalLink, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { JobListing } from "@/data/mockData";

interface Props {
  jobs: JobListing[];
  onSave: (id: string) => void;
  onApply: (id: string) => void;
  onSelect: (job: JobListing) => void;
}

export function JobTable({ jobs, onSave, onApply, onSelect }: Props) {
  return (
    <div className="rounded-lg border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="font-semibold">Position</TableHead>
            <TableHead className="font-semibold">Company</TableHead>
            <TableHead className="font-semibold">Location</TableHead>
            <TableHead className="font-semibold">Salary</TableHead>
            <TableHead className="font-semibold text-center">Score</TableHead>
            <TableHead className="font-semibold text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => {
            const scoreColor = job.relevanceScore >= 85 ? "text-success" : job.relevanceScore >= 70 ? "text-warning" : "text-muted-foreground";
            return (
              <TableRow
                key={job.id}
                className="cursor-pointer hover:bg-muted/30"
                onClick={() => onSelect(job)}
              >
                <TableCell>
                  <div>
                    <p className="font-medium text-card-foreground">{job.title}</p>
                    <div className="flex gap-1.5 mt-1">
                      <Badge variant="secondary" className="text-[10px]">{job.type}</Badge>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-sm">{job.company}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{job.location}</TableCell>
                <TableCell className="text-sm">{job.salary}</TableCell>
                <TableCell className="text-center">
                  <span className={`font-bold text-sm ${scoreColor}`}>
                    {job.relevanceScore}%
                  </span>
                </TableCell>
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => onSave(job.id)}
                    >
                      {job.saved ? (
                        <BookmarkCheck className="h-3.5 w-3.5 text-primary" />
                      ) : (
                        <Bookmark className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      className="h-8"
                      onClick={() => onApply(job.id)}
                      disabled={job.applied}
                    >
                      {job.applied ? "Applied" : "Apply"}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
