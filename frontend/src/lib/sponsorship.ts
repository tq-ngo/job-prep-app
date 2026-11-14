export type SponsorshipStatus = "cpt_opt" | "h1b" | "citizenship" | "no_sponsorship";

export interface SponsorshipInfo {
  status: SponsorshipStatus;
  label: string;
  isCitizenOnly: boolean;
  isF1Eligible: boolean;
}

const CITIZEN_REGEX = /\b(?:u\.?s\.?\s+citizen(?:ship)?\s+(?:required|only|status)|must be a u\.?s\.?\s+citizen|u\.?s\.?\s+person\b|security clearance\b|active secret clearance\b|itar\b|export control laws?\b)/i;
const NO_SPONSOR_REGEX = /\b(?:will not sponsor|does not sponsor|no visa sponsorship|not eligible for (?:visa\s+)?sponsorship|without (?:the\s+)?need for (?:visa\s+)?sponsorship|sponsorship is not available)\b/i;
const H1B_REGEX = /\b(?:visa sponsorship (?:is\s+)?available|h-?1b sponsorship|offers? (?:visa\s+)?sponsorship|will sponsor (?:work\s+)?visas?|provides? (?:visa\s+)?sponsorship)\b/i;
const CPT_OPT_REGEX = /\b(?:cpt|opt|f-?1\s+visa|f-?1\s+students?|stem\s+opt)\b/i;

/**
 * Determine sponsorship classification for a job, using backend metadata if present
 * or evaluating title and description heuristics.
 */
export function getJobSponsorship(job: {
  title: string;
  description?: string | null;
  sponsorship_status?: string | null;
  sponsorship_label?: string | null;
}): SponsorshipInfo {
  if (job.sponsorship_status && job.sponsorship_label) {
    const status = job.sponsorship_status as SponsorshipStatus;
    return {
      status,
      label: job.sponsorship_label,
      isCitizenOnly: status === "citizenship",
      isF1Eligible: status === "cpt_opt" || status === "h1b",
    };
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

  if (H1B_REGEX.test(text)) {
    return {
      status: "h1b",
      label: "H-1B Sponsor",
      isCitizenOnly: false,
      isF1Eligible: true,
    };
  }

  if (NO_SPONSOR_REGEX.test(text)) {
    return {
      status: "no_sponsorship",
      label: "No Sponsorship",
      isCitizenOnly: false,
      isF1Eligible: false,
    };
  }

  if (CPT_OPT_REGEX.test(text)) {
    return {
      status: "cpt_opt",
      label: "CPT/OPT Sponsor",
      isCitizenOnly: false,
      isF1Eligible: true,
    };
  }

  // Default for general campus postings with no citizenship gate:
  return {
    status: "cpt_opt",
    label: "CPT/OPT Sponsor",
    isCitizenOnly: false,
    isF1Eligible: true,
  };
}

