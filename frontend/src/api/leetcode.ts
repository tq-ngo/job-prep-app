import apiClient from "@/lib/api-client";
import { LeetCodeSubmission } from "@/types";

export const submitLeetCode = async (submission: LeetCodeSubmission): Promise<LeetCodeSubmission> => {
  const response = await apiClient.post<LeetCodeSubmission>("/leetcode/submit", submission);
  return response.data;
};

export const getReviewQueue = async (): Promise<LeetCodeSubmission[]> => {
  const response = await apiClient.get<LeetCodeSubmission[]>("/leetcode/review-queue");
  return response.data;
};
