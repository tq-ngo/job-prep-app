import axios from "axios";
import { API_BASE, googleLoginUrl } from "./urls";

export { API_BASE };

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  // Send the HttpOnly auth cookies on every request. Tokens are no longer
  // held in localStorage, where any XSS could read them.
  withCredentials: true,
});

/** Read a non-HttpOnly cookie (only the CSRF token is readable by design). */
function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)")
  );
  return match ? decodeURIComponent(match[1]) : null;
}

// Echo the CSRF cookie back in a header (double-submit). The browser attaches
// the auth cookie automatically, so state-changing calls need this second
// factor that a cross-origin attacker cannot read or set.
apiClient.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (!["get", "head", "options"].includes(method)) {
    const csrf = readCookie("csrf_token");
    if (csrf && config.headers) config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

// Transparently refresh an expired access token, then replay the request.
// Access tokens are short-lived (15 min), so without this every session
// would bounce to /login a quarter of an hour after signing in.
let refreshPromise: Promise<unknown> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url: string = original?.url || "";
    const isAuthCall =
      url.includes("/auth/login") ||
      url.includes("/auth/refresh") ||
      url.includes("/auth/register");
    const isMeCall = url.includes("/auth/me");

    // Only attempt refresh if:
    // 1. Status is 401
    // 2. Not already retried
    // 3. Not an auth call (login, refresh, register)
    // 4. A session actually exists (indicated by the csrf_token cookie). If there's no
    //    CSRF cookie, the user is unauthenticated — do NOT spam /refresh or trigger reload loops.
    const hasSessionCookie = Boolean(readCookie("csrf_token"));

    if (status === 401 && !isAuthCall && !original?._retried && hasSessionCookie) {
      original._retried = true;
      try {
        // Collapse concurrent 401s into a single refresh call.
        refreshPromise =
          refreshPromise || apiClient.post("/api/v1/auth/refresh");
        await refreshPromise;
        refreshPromise = null;
        return apiClient(original);
      } catch {
        refreshPromise = null;
        // Never redirect if this was an identity check (/auth/me) or if we are already
        // on a public or auth route (/login, /register, /).
        if (!isMeCall && typeof window !== "undefined") {
          const currentPath = window.location.pathname;
          if (
            currentPath !== "/login" &&
            currentPath !== "/register" &&
            currentPath !== "/"
          ) {
            window.location.href = `/login?next=${encodeURIComponent(
              currentPath + window.location.search
            )}`;
          }
        }
      }
    }
    return Promise.reject(error);
  }
);

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
  /** "hour" | "year"; internship pay is usually hourly. */
  salary_period?: "hour" | "year" | null;
  category?: string | null;
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

/** Payload of a live `job` SSE event (see backend app/core/events.py). */
export interface JobEvent {
  kind: "created" | "enriched";
  id: string;
  title: string;
  company: string;
  location: string | null;
  skills: string[];
  apply_url: string;
  source: string;
  is_remote: boolean | null;
}

/** A feed row: the list endpoint omits `description` (fetched per job). */
export type JobSummary = Omit<Job, "description">;

export interface JobListResponse {
  items: JobSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  /** True when `total` hit the server's display cap (render as "500+"). */
  capped?: boolean;
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
  getStatus: async (taskId: string): Promise<{
    status: string;
    result: unknown;
    error: string | null;
    meta?: { percent: number; message: string };
  }> => {
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
    const params = new URLSearchParams();
    params.append("username", email);
    params.append("password", password);
    // The response body no longer contains a token: the server sets
    // HttpOnly cookies instead. It returns the CSRF token for the
    // double-submit header.
    const { data } = await apiClient.post<{ status: string; csrf_token: string }>(
      "/api/v1/auth/login",
      params,
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    );
    return data;
  },
  logout: async () => {
    await apiClient.post("/api/v1/auth/logout");
  },
  /** Rotate the session cookies. Rejects when the session is gone. */
  refresh: async () => {
    await apiClient.post("/api/v1/auth/refresh");
  },
  /** True when a session probably exists (the readable CSRF cookie is set). */
  hasSessionHint: () => Boolean(readCookie("csrf_token")),
  googleLoginUrl,
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
  scraped_at: string;
  summary: string | null;
  categories: string[] | null;
  tags: string[] | null;
  /** Null while the AI summary is queued; `summary` is the page's own blurb. */
  enriched_at: string | null;
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
  triggerLinkedInNews: async (): Promise<{ task_id: string; status: string }> => {
    const { data } = await apiClient.post("/api/v1/news/scrape/linkedin");
    return data;
  },
};