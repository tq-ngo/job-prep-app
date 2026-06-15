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
