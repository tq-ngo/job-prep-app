import { describe, expect, it } from "vitest";
import { getJobSponsorship } from "@/lib/sponsorship";

describe("getJobSponsorship (src/lib/sponsorship.ts)", () => {
  it("uses backend sponsorship_status even when sponsorship_label is null", () => {
    expect(
      getJobSponsorship({
        title: "SWE Intern",
        sponsorship_status: "no_sponsorship",
        sponsorship_label: null,
      }),
    ).toEqual({
      status: "no_sponsorship",
      label: "No Sponsorship",
      isCitizenOnly: false,
      isF1Eligible: false,
    });

    expect(
      getJobSponsorship({
        title: "SWE Intern",
        sponsorship_status: "citizenship",
        sponsorship_label: null,
      }),
    ).toEqual({
      status: "citizenship",
      label: "US Citizen Required",
      isCitizenOnly: true,
      isF1Eligible: false,
    });
  });

  it("detects no_sponsorship from description heuristics", () => {
    expect(
      getJobSponsorship({
        title: "Backend Intern",
        description: "We will not sponsor work visas for this internship.",
      }),
    ).toEqual({
      status: "no_sponsorship",
      label: "No Sponsorship",
      isCitizenOnly: false,
      isF1Eligible: false,
    });
  });

  it("does not misclassify 'with or without sponsorship' as no_sponsorship", () => {
    expect(
      getJobSponsorship({
        title: "Software Engineering Intern",
        description: "All candidates authorized to work with or without sponsorship are encouraged to apply.",
      }),
    ).toBeNull();
  });
});
