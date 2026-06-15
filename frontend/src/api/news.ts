import apiClient from "@/lib/api-client";
import { CorporateNewsItem } from "@/types";

export const getNews = async (): Promise<CorporateNewsItem[]> => {
  const response = await apiClient.get<CorporateNewsItem[]>("/news/");
  return response.data;
};

export const ingestNews = async (item: Partial<CorporateNewsItem>): Promise<CorporateNewsItem> => {
  const response = await apiClient.post<CorporateNewsItem>("/news/ingest", item);
  return response.data;
};
