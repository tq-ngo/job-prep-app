import { describe, expect, it } from "vitest";
import { formatPay, formatPostedAgo } from "@/lib/format";
import { parseJobFilters, sameFilters, toListParams } from "@/lib/job-filters";

describe("formatPay", () => {
  it("formats hourly, annual and single values", () => {
    expect(formatPay({ salary_min: 60, salary_max: 75, salary_period: "hour" })).toBe("$60 – $75/hr");
    expect(formatPay({ salary_min: 120000, salary_max: 130000, salary_period: "year" })).toBe("$120,000 – $130,000/yr");
    expect(formatPay({ salary_min: 50, salary_max: 50, salary_period: null })).toBe("$50");
    expect(formatPay({ salary_min: null, salary_max: 90, salary_period: "hour" })).toBe("$90/hr");
  });

  it("returns null when pay isn't listed", () => {
    expect(formatPay({ salary_min: null, salary_max: null, salary_period: null })).toBeNull();
  });
});

describe("formatPostedAgo", () => {
  const now = Date.parse("2026-03-20T12:00:00Z");
  it.each([
    ["2026-03-20T00:00:00Z", "today"],
    ["2026-03-19T06:00:00Z", "yesterday"],
    ["2026-03-17T00:00:00Z", "3 days ago"],
    ["2026-03-10T00:00:00Z", "last week"],
    ["2026-01-10T00:00:00Z", "2 months ago"],
    ["2026-03-21T00:00:00Z", "today"], // a little in the future (time zones)
  ])("%s → %s", (iso, expected) => {
    expect(formatPostedAgo(iso, now)).toBe(expected);
  });
});

describe("parseJobFilters", () => {
  const parse = (qs: string) => parseJobFilters((k) => new URLSearchParams(qs).get(k));

  it("reads every filter", () => {
    expect(parse("q=%20rust%20&category=Quant&source=linkedin&remote=true&page=3")).toEqual({
      q: "rust",
      category: "Quant",
      source: "linkedin",
      remote: true,
      page: 3,
    });
  });

  it("drops values the API wouldn't accept instead of sending them", () => {
    expect(parse("category=Nope&source=indeed&remote=yes&page=-2")).toEqual({
      q: "",
      category: "",
      source: "",
      remote: false,
      page: 1,
    });
    expect(parse(`q=${"x".repeat(300)}`).q).toHaveLength(200);
  });

  it("builds API params with only the set filters", () => {
    expect(toListParams(parse("category=FAANG%2B&remote=1"))).toEqual({
      page: 1,
      page_size: 30,
      category: "FAANG+",
      is_remote: true,
    });
  });

  it("compares filter sets", () => {
    expect(sameFilters(parse("q=a&page=2"), parse("page=2&q=a"))).toBe(true);
    expect(sameFilters(parse("q=a"), parse("q=a&page=2"))).toBe(false);
  });
});
