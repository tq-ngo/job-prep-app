import { describe, expect, it } from "vitest";
import { apiErrorMessage, NETWORK_ERROR, RATE_LIMITED } from "@/lib/errors";

const fallback = "Something went wrong.";

describe("apiErrorMessage", () => {
  it("recognises an unreachable server", () => {
    expect(apiErrorMessage({ request: {}, code: "ERR_NETWORK" }, { fallback })).toBe(NETWORK_ERROR);
  });

  it("recognises rate limiting", () => {
    expect(apiErrorMessage({ response: { status: 429 } }, { fallback })).toBe(RATE_LIMITED);
  });

  it("prefers a caller's message for a status", () => {
    expect(apiErrorMessage({ response: { status: 401, data: { detail: "x" } } }, { byStatus: { 401: "Wrong password." }, fallback })).toBe("Wrong password.");
  });

  it("shows a 4xx detail, such as the SSRF guard's reason", () => {
    const err = { response: { status: 400, data: { detail: "URL resolves to a private address" } } };
    expect(apiErrorMessage(err, { fallback })).toBe("URL resolves to a private address");
  });

  it("joins Pydantic validation messages without their prefix", () => {
    const err = {
      response: {
        status: 422,
        data: { detail: [{ msg: "Value error, Password must contain at least one digit" }, { msg: "Field required" }] },
      },
    };
    expect(apiErrorMessage(err, { fallback })).toBe("Password must contain at least one digit. Field required.");
  });

  it("never shows a 5xx detail", () => {
    expect(apiErrorMessage({ response: { status: 500, data: { detail: "psycopg error at ..." } } }, { fallback })).toBe(fallback);
  });

  it("falls back for anything else", () => {
    expect(apiErrorMessage(new Error("boom"), { fallback })).toBe(fallback);
  });
});
