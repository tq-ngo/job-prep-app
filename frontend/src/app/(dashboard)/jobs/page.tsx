"use client";

import { useQuery } from "@tanstack/react-query";
import { getJobs } from "@/api/jobs";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, Briefcase } from "lucide-react";
import SyncButton from "@/components/jobs/sync-button";

export default function JobsPage() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: getJobs,
  });

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "applied": return "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20";
      case "interviewing": return "bg-orange-500/10 text-orange-500 hover:bg-orange-500/20";
      case "rejected": return "bg-red-500/10 text-red-500 hover:bg-red-500/20";
      case "offer": return "bg-green-500/10 text-green-500 hover:bg-green-500/20";
      default: return "bg-slate-500/10 text-slate-500 hover:bg-slate-500/20";
    }
  };

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Job Applications</h2>
          <p className="text-muted-foreground">
            Manage and track your job applications across different platforms.
          </p>
        </div>
        <SyncButton />
      </div>

      <div className="rounded-md border bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Date Applied</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10">
                  Loading jobs...
                </TableCell>
              </TableRow>
            ) : jobs?.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10">
                  <div className="flex flex-col items-center gap-2">
                    <Briefcase className="h-8 w-8 text-muted-foreground" />
                    <p>No job applications found. Click sync to fetch new posts.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              jobs?.map((job) => (
                <TableRow key={job.id}>
                  <TableCell className="font-medium">{job.company_name}</TableCell>
                  <TableCell>{job.job_title}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{job.source}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={getStatusColor(job.status)} variant="secondary">
                      {job.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{new Date(job.date_applied).toLocaleDateString()}</TableCell>
                  <TableCell className="text-right">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => window.open(job.job_url, "_blank")}
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
