import axios from "axios";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to requests
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  source: string;
  apply_url: string;
  description: string | null;
  skills: string[] | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  is_remote: boolean | null;
  posted_at: string | null;
  scraped_at: string;
  is_active?: boolean;
  seniority_level?: string | null;
  employment_type?: string | null;
  external_id?: string;
  source_url?: string | null;
  terms?: string[] | null;
}

export interface JobListResponse {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export const jobsApi = {
  list: async (params: {
    page?: number;
    page_size?: number;
    source?: string;
    is_remote?: boolean;
    q?: string;
    category?: string;
  }): Promise<JobListResponse> => {
    const { data } = await apiClient.get("/api/v1/jobs/", { params });
    return data;
  },

  get: async (id: string): Promise<Job> => {
    const { data } = await apiClient.get(`/api/v1/jobs/${id}`);
    return data;
  },

  triggerScrape: async (source: string): Promise<{ task_id: string; status: string }> => {
    const { data } = await apiClient.post(`/api/v1/jobs/scrape/${source}`);
    return data;
  },
};

export const tasksApi = {
  getStatus: async (taskId: string): Promise<{ status: string; result: any; error: string | null; meta?: any }> => {
    const { data } = await apiClient.get(`/api/v1/tasks/${taskId}`);
    return data;
  },
};

export interface User {
  id: number;
  email: string;
  skills: string[];
}

export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);
    const { data } = await apiClient.post<{ access_token: string; token_type: string }>("/api/v1/auth/login", formData);
    return data;
  },
  register: async (email: string, password: string) => {
    const { data } = await apiClient.post<User>("/api/v1/auth/register", { email, password });
    return data;
  },
  getMe: async () => {
    const { data } = await apiClient.get<User>("/api/v1/auth/me");
    return data;
  },
  updateSkills: async (skills: string[]) => {
    const { data } = await apiClient.put<User>("/api/v1/auth/me/skills", { skills });
    return data;
  },
};

export interface NewsArticle {
  id: string;
  title: string | null;
  url: string;
  source_domain: string;
  published_at: string | null;
  summary: string | null;
  categories: string[] | null;
}

export const newsApi = {
  list: async (): Promise<NewsArticle[]> => {
    const { data } = await apiClient.get("/api/v1/news/");
    return data;
  },
  triggerScrape: async (url: string) => {
    const { data } = await apiClient.post("/api/v1/news/scrape", null, { params: { url } });
    return data;
  },
};