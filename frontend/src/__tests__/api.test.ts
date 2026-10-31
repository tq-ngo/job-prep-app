import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { AxiosError, InternalAxiosRequestConfig } from "axios";
import { apiClient, jobsApi, authApi, newsApi } from "@/lib/api";

function clearAllCookies() {
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const eqPos = cookie.indexOf("=");
    const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/;`;
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT;`;
    }
  }
}

describe("API Client & Interceptors (src/lib/api.ts)", () => {
  const originalAdapter = apiClient.defaults.adapter;

  beforeEach(() => {
    clearAllCookies();
  });

  afterEach(() => {
    clearAllCookies();
    apiClient.defaults.adapter = originalAdapter;
    vi.restoreAllMocks();
  });

  describe("Request Interceptor (CSRF Double-Submit)", () => {
    it("injects X-CSRF-Token header on mutating POST request when csrf_token cookie exists", async () => {
      document.cookie = "csrf_token=test-csrf-123; path=/";
      let capturedConfig: InternalAxiosRequestConfig | null = null;

      apiClient.defaults.adapter = async (config) => {
        capturedConfig = config;
        return {
          data: { task_id: "t-1", status: "started" },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      };

      await jobsApi.triggerScrape("github");
      expect(capturedConfig).toBeDefined();
      expect(capturedConfig!.headers["X-CSRF-Token"]).toBe("test-csrf-123");
    });

    it("omits X-CSRF-Token header on GET requests even if csrf_token cookie is present", async () => {
      document.cookie = "csrf_token=test-csrf-123; path=/";
      let capturedConfig: InternalAxiosRequestConfig | null = null;

      apiClient.defaults.adapter = async (config) => {
        capturedConfig = config;
        return {
          data: { items: [], total: 0, page: 1, page_size: 30, pages: 0 },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      };

      await jobsApi.list({});
      expect(capturedConfig).toBeDefined();
      expect(capturedConfig!.headers["X-CSRF-Token"]).toBeUndefined();
    });

    it("does not inject X-CSRF-Token if csrf_token cookie is absent", async () => {
      let capturedConfig: InternalAxiosRequestConfig | null = null;

      apiClient.defaults.adapter = async (config) => {
        capturedConfig = config;
        return {
          data: { task_id: "t-2", status: "started" },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      };

      await jobsApi.triggerScrape("linkedin");
      expect(capturedConfig).toBeDefined();
      expect(capturedConfig!.headers["X-CSRF-Token"]).toBeUndefined();
    });
  });

  describe("Response Interceptor (401 Refresh & Replay)", () => {
    it("transparently refreshes session and replays original request on 401 when session hint exists", async () => {
      document.cookie = "csrf_token=valid-session; path=/";
      let jobGetAttempts = 0;
      let refreshCalls = 0;

      apiClient.defaults.adapter = async (config) => {
        const url = config.url || "";
        if (url.includes("/api/v1/auth/refresh")) {
          refreshCalls++;
          return {
            data: { status: "success" },
            status: 200,
            statusText: "OK",
            headers: {},
            config,
          };
        }

        if (url.includes("/api/v1/jobs/job-123")) {
          jobGetAttempts++;
          if (jobGetAttempts === 1) {
            const err = new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
              status: 401,
              statusText: "Unauthorized",
              headers: {},
              config,
              data: {},
            });
            throw err;
          }
          return {
            data: { id: "job-123", title: "SWE Intern", company: "Google" },
            status: 200,
            statusText: "OK",
            headers: {},
            config,
          };
        }

        return {
          data: {},
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      };

      const job = await jobsApi.get("job-123");
      expect(refreshCalls).toBe(1);
      expect(jobGetAttempts).toBe(2);
      expect(job.title).toBe("SWE Intern");
    });

    it("collapses concurrent 401 requests into a single /auth/refresh call", async () => {
      document.cookie = "csrf_token=valid-session; path=/";
      let refreshCount = 0;
      let listAttempts = 0;
      let getAttempts = 0;

      apiClient.defaults.adapter = async (config) => {
        const url = config.url || "";
        if (url.includes("/api/v1/auth/refresh")) {
          refreshCount++;
          await new Promise((r) => setTimeout(r, 20));
          return {
            data: { status: "success" },
            status: 200,
            statusText: "OK",
            headers: {},
            config,
          };
        }

        if (url.includes("/api/v1/jobs/concurrent-test")) {
          getAttempts++;
          if (getAttempts === 1) {
            throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
              status: 401,
              statusText: "Unauthorized",
              headers: {},
              config,
              data: {},
            });
          }
          return {
            data: { id: "concurrent-test", title: "Product Intern" },
            status: 200,
            statusText: "OK",
            headers: {},
            config,
          };
        }

        if (url.includes("/api/v1/jobs/")) {
          listAttempts++;
          if (listAttempts === 1) {
            throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
              status: 401,
              statusText: "Unauthorized",
              headers: {},
              config,
              data: {},
            });
          }
          return {
            data: { items: [], total: 0 },
            status: 200,
            statusText: "OK",
            headers: {},
            config,
          };
        }

        return {
          data: {},
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      };

      const [, getRes] = await Promise.all([
        jobsApi.list({}),
        jobsApi.get("concurrent-test"),
      ]);

      expect(refreshCount).toBe(1);
      expect(listAttempts).toBe(2);
      expect(getAttempts).toBe(2);
      expect(getRes.title).toBe("Product Intern");
    });

    it("does not attempt refresh if request was already retried", async () => {
      document.cookie = "csrf_token=valid-session; path=/";
      let refreshCalls = 0;

      apiClient.defaults.adapter = async (config) => {
        const url = config.url || "";
        if (url.includes("/api/v1/auth/refresh")) {
          refreshCalls++;
          return { data: {}, status: 200, statusText: "OK", headers: {}, config };
        }
        (config as InternalAxiosRequestConfig & { _retried?: boolean })._retried = true;
        throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
          status: 401,
          statusText: "Unauthorized",
          headers: {},
          config,
          data: {},
        });
      };

      await expect(jobsApi.get("any-id")).rejects.toThrow("Unauthorized");
      expect(refreshCalls).toBe(0);
    });

    it("does not attempt refresh for login endpoint", async () => {
      document.cookie = "csrf_token=valid-session; path=/";
      let refreshCalls = 0;

      apiClient.defaults.adapter = async (config) => {
        const url = config.url || "";
        if (url.includes("/api/v1/auth/refresh")) {
          refreshCalls++;
          return { data: {}, status: 200, statusText: "OK", headers: {}, config };
        }
        throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
          status: 401,
          statusText: "Unauthorized",
          headers: {},
          config,
          data: {},
        });
      };

      await expect(authApi.login("user@test.com", "pass")).rejects.toThrow("Unauthorized");
      expect(refreshCalls).toBe(0);
    });
  });

  describe("API Resource Endpoints", () => {
    it("jobsApi.list formats query parameters", async () => {
      let passedParams: Record<string, unknown> | undefined;
      apiClient.defaults.adapter = async (config) => {
        passedParams = config.params;
        return {
          data: { items: [], total: 0, page: 2, page_size: 50, pages: 1 },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      };

      await jobsApi.list({ page: 2, page_size: 50, category: "FAANG+", is_remote: true });
      expect(passedParams).toEqual({
        page: 2,
        page_size: 50,
        category: "FAANG+",
        is_remote: true,
      });
    });

    it("authApi.hasSessionHint accurately checks csrf_token existence", () => {
      clearAllCookies();
      expect(authApi.hasSessionHint()).toBe(false);

      document.cookie = "csrf_token=valid_token; path=/;";
      expect(authApi.hasSessionHint()).toBe(true);
    });

    it("newsApi.list retrieves news articles", async () => {
      const mockArticles = [
        { id: "1", title: "New AI Model", url: "https://example.com/ai", source_domain: "example.com" },
      ];
      apiClient.defaults.adapter = async (config) => ({
        data: mockArticles,
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      });

      const result = await newsApi.list();
      expect(result).toHaveLength(1);
      expect(result[0].title).toBe("New AI Model");
    });
  });
});
