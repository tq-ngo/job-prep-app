import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";

describe("ThemeContext (src/context/ThemeContext.tsx)", () => {
  beforeEach(() => {
    document.documentElement.className = "";
    localStorage.clear();
  });

  afterEach(() => {
    document.documentElement.className = "";
    localStorage.clear();
  });

  it("throws error when useTheme is called outside ThemeProvider", () => {
    expect(() => renderHook(() => useTheme())).toThrow(
      "useTheme must be used within a ThemeProvider"
    );
  });

  it("defaults to 'light' when no dark class is present on documentElement", () => {
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
    expect(result.current.theme).toBe("light");
  });

  it("detects 'dark' theme when documentElement already has dark class", () => {
    document.documentElement.classList.add("dark");
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
    expect(result.current.theme).toBe("dark");
  });

  it("toggleTheme switches from light to dark, toggles class and stores in localStorage", async () => {
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
    expect(result.current.theme).toBe("light");

    await act(async () => {
      result.current.toggleTheme();
    });

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("jobprep_theme")).toBe("dark");
    await waitFor(() => expect(result.current.theme).toBe("dark"));

    await act(async () => {
      result.current.toggleTheme();
    });

    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("jobprep_theme")).toBe("light");
    await waitFor(() => expect(result.current.theme).toBe("light"));
  });

  it("setTheme explicitly sets chosen theme", async () => {
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });

    await act(async () => {
      result.current.setTheme("dark");
    });
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("jobprep_theme")).toBe("dark");
    await waitFor(() => expect(result.current.theme).toBe("dark"));

    await act(async () => {
      result.current.setTheme("light");
    });
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("jobprep_theme")).toBe("light");
    await waitFor(() => expect(result.current.theme).toBe("light"));
  });
});
