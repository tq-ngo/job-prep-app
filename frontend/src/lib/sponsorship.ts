export type SponsorshipStatus = "sponsorship_available" | "citizenship" | "no_sponsorship";

export interface SponsorshipInfo {
  status: SponsorshipStatus;
  label: string;
  isCitizenOnly: boolean;
  isF1Eligible: boolean;
}

const CITIZEN_REGEX =
  /\b(?:u\.?s\.?\s+citizen(?:ship)?\s+(?:required|only|is required|mandatory)|must be a u\.?s\.?\s+citizen|you are a u\.?s\.?\s+citizen|u\.?s\.?\s+citizen(?:ship)?\s*,\s*(?:u\.?s\.?\s+)?permanent resident|u\.?s\.?\s+citizen(?:ship)?\s+(?:or|and)\s+(?:u\.?s\.?\s+)?permanent resident|u\.?s\.?\s+person\b|security clearance\b|active secret clearance\b|top secret\b|dod clearance\b|itar\b|export control laws?\b)/i;
const WITH_OR_WITHOUT_SPONSOR_REGEX = /\bwith\s+or\s+without\s+(?:[\w\s]{0,30}\s+)?sponsorship\b/i;
const NO_SPONSOR_REGEX =
  /\b(?:will not sponsor|does not sponsor|no visa sponsorship|not eligible for (?:visa\s+)?sponsorship|without (?:the\s+)?need for (?:visa\s+)?sponsorship|sponsorship (?:is\s+)?not available|must not require (?:work\s+)?(?:visa\s+)?sponsorship|without\s+(?:[\w\s]{1,30}\s+)?sponsorship|not provide (?:visa\s+|work\s+)?sponsorship|(?:f-?1|cpt|opt|j-?1|m-?1).*?not eligible)\b/i;
const SPONSOR_AVAILABLE_REGEX =
  /\b(?:visa sponsorship (?:is\s+)?available|offers? (?:visa\s+)?sponsorship|will sponsor (?:work\s+)?visas?|provides? (?:visa\s+)?sponsorship|h-?1b (?:sponsorship|sponsor|visa support)|sponsors? h-?1b|accepts?\s+(?:cpt|opt)|(?:cpt|opt)\s+accepted|cpt\/opt\s+eligible|f-?1\s+visa\s+sponsorship)\b/i;

/**
 * Determine sponsorship classification for a job, using backend metadata if present
 * or evaluating title and description heuristics.
 * Returns null if sponsorship/citizenship is not confirmed.
 */
export function getJobSponsorship(job: {
  title: string;
  description?: string | null;
  sponsorship_status?: string | null;
  sponsorship_label?: string | null;
}): SponsorshipInfo | null {
  if (job.sponsorship_status) {
    if (job.sponsorship_status === "citizenship") {
      return {
        status: "citizenship",
        label: job.sponsorship_label || "US Citizen Required",
        isCitizenOnly: true,
        isF1Eligible: false,
      };
    }
    if (job.sponsorship_status === "no_sponsorship") {
      return {
        status: "no_sponsorship",
        label: job.sponsorship_label || "No Sponsorship",
        isCitizenOnly: false,
        isF1Eligible: false,
      };
    }
    if (
      job.sponsorship_status === "sponsorship_available" ||
      job.sponsorship_status === "cpt_opt" ||
      job.sponsorship_status === "h1b"
    ) {
      return {
        status: "sponsorship_available",
        label: job.sponsorship_label || "Sponsorship Available",
        isCitizenOnly: false,
        isF1Eligible: true,
      };
    }
    return null;
  }

  const text = `${job.title} ${job.description || ""}`;

  if (CITIZEN_REGEX.test(text)) {
    return {
      status: "citizenship",
      label: "US Citizen Required",
      isCitizenOnly: true,
      isF1Eligible: false,
    };
  }

  if (SPONSOR_AVAILABLE_REGEX.test(text)) {
    return {
      status: "sponsorship_available",
      label: "Sponsorship Available",
      isCitizenOnly: false,
      isF1Eligible: true,
    };
  }

  // Avoid flagging inclusive equal-opportunity phrasing like "with or without sponsorship"
  const scrubbedText = text.replace(WITH_OR_WITHOUT_SPONSOR_REGEX, "");
  if (NO_SPONSOR_REGEX.test(scrubbedText)) {
    return {
      status: "no_sponsorship",
      label: "No Sponsorship",
      isCitizenOnly: false,
      isF1Eligible: false,
    };
  }

  // Not explicitly confirmed: leave untagged
  return null;
}
