import apiClient from "@/lib/api-client";
import { JobApplication, SyncResponse, SyncStatus } from "@/types";

export const getJobs = async (): Promise<JobApplication[]> => {
  const response = await apiClient.get<JobApplication[]>("/jobs/");
  return response.data;
};

export const triggerSimplifySync = async (): Promise<SyncResponse> => {
  const response = await apiClient.post<SyncResponse>("/jobs/trigger-sync");
  return response.data;
};

export const triggerLinkedInSync = async (searchUrl: string): Promise<SyncResponse> => {
  const response = await apiClient.post<SyncResponse>(`/jobs/trigger-linkedin-sync?search_url=${encodeURIComponent(searchUrl)}`);
  return response.data;
};

export const getSyncStatus = async (taskId: string): Promise<SyncStatus> => {
  const response = await apiClient.get<SyncStatus>(`/jobs/sync-status/${taskId}`);
  return response.data;
};

export const getSyncStreamUrl = (taskId: string): string => {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  return `${baseUrl}/jobs/sync-stream/${taskId}`;
};

export const searchJobs = async (
  q?: string,
  skills?: string,
  remoteOnly?: boolean,
  minSalary?: number
): Promise<any[]> => {
  const params = new URLSearchParams();
  if (q) params.append("q", q);
  if (skills) params.append("skills", skills);
  if (remoteOnly) params.append("remote_only", "true");
  if (minSalary) params.append("min_salary", minSalary.toString());

  const response = await apiClient.get<any[]>(`/jobs/search?${params.toString()}`);
  return response.data;
};

export const trackJob = async (jobId: string, status: string = "Applied"): Promise<any> => {
  const response = await apiClient.post(`/jobs/${jobId}/track?status_str=${encodeURIComponent(status)}`);
  return response.data;
};
