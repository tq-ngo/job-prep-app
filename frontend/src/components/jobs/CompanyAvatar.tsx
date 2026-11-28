"use client";

import { useState } from "react";
import { cn } from "@/components/ui/cn";

const KNOWN_DOMAINS: Record<string, string> = {
  tesla: "tesla.com",
  google: "google.com",
  alphabet: "google.com",
  meta: "meta.com",
  facebook: "meta.com",
  apple: "apple.com",
  amazon: "amazon.com",
  aws: "amazon.com",
  microsoft: "microsoft.com",
  netflix: "netflix.com",
  stripe: "stripe.com",
  citadel: "citadel.com",
  "citadel securities": "citadelsecurities.com",
  lightmatter: "lightmatter.co",
  tiktok: "tiktok.com",
  bytedance: "bytedance.com",
  uber: "uber.com",
  airbnb: "airbnb.com",
  nvidia: "nvidia.com",
  amd: "amd.com",
  intel: "intel.com",
  ibm: "ibm.com",
  salesforce: "salesforce.com",
  spotify: "spotify.com",
  palantir: "palantir.com",
  databricks: "databricks.com",
  snowflake: "snowflake.com",
  roblox: "roblox.com",
  pinterest: "pinterest.com",
  snap: "snap.com",
  snapchat: "snap.com",
  doordash: "doordash.com",
  coinbase: "coinbase.com",
  robinhood: "robinhood.com",
  reddit: "reddit.com",
  twitter: "x.com",
  x: "x.com",
  linkedin: "linkedin.com",
  github: "github.com",
  cisco: "cisco.com",
  oracle: "oracle.com",
  adobe: "adobe.com",
  bloomberg: "bloomberg.com",
  "two sigma": "twosigma.com",
  "jane street": "janestreet.com",
  "hudson river trading": "hudsonrivertrading.com",
  hrt: "hudsonrivertrading.com",
  "jump trading": "jumptrading.com",
  optiver: "optiver.com",
  imc: "imc.com",
  drw: "drw.com",
  "akuna capital": "akunacapital.com",
  "de shaw": "deshaw.com",
  point72: "point72.com",
  millennium: "mlp.com",
  bridgewater: "bridgewater.com",
  "goldman sachs": "goldmansachs.com",
  "morgan stanley": "morganstanley.com",
  "jpmorgan chase": "jpmorgan.com",
  jpmorgan: "jpmorgan.com",
  "bank of america": "bankofamerica.com",
  vallen: "vallen.com",
  "vallen usa": "vallen.com",
  "r.s. hughes": "rshughes.com",
  "r.s. hughes co., inc.": "rshughes.com",
  "xcel energy": "xcelenergy.com",
  nextera: "nexteraenergy.com",
  "nextera energy": "nexteraenergy.com",
  verisk: "verisk.com",
  bmll: "bmlltech.com",
  "bmll technologies": "bmlltech.com",
  merrick: "merrick.com",
  motorola: "motorola.com",
  "motorola solutions": "motorolasolutions.com",
  nbc: "nbcuniversal.com",
  nbcuniversal: "nbcuniversal.com",
  "general dynamics": "gdmissionsystems.com",
  "general dynamics mission systems": "gdmissionsystems.com",
  conductorai: "conductorai.com",
  "the toro company": "thetorocompany.com",
  toro: "thetorocompany.com",
  wtw: "wtwco.com",
  atlassian: "atlassian.com",
  slack: "slack.com",
  zoom: "zoom.us",
  dropbox: "dropbox.com",
  box: "box.com",
  figma: "figma.com",
  canva: "canva.com",
  notion: "notion.so",
  discord: "discord.com",
  affirm: "affirm.com",
  plaid: "plaid.com",
  ramp: "ramp.com",
  brex: "brex.com",
  gusto: "gusto.com",
  chime: "chime.com",
  scale: "scale.com",
  "scale ai": "scale.com",
  openai: "openai.com",
  anthropic: "anthropic.com",
  cohere: "cohere.com",
  waymo: "waymo.com",
  cruise: "getcruise.com",
  spacex: "spacex.com",
  anduril: "anduril.com",
  "anduril industries": "anduril.com",
  lockheed: "lockheedmartin.com",
  "lockheed martin": "lockheedmartin.com",
  boeing: "boeing.com",
  northrop: "northropgrumman.com",
  "northrop grumman": "northropgrumman.com",
  raytheon: "rtx.com",
  rtx: "rtx.com",
  general: "ge.com",
  "general electric": "ge.com",
  ford: "ford.com",
  gm: "gm.com",
  "general motors": "gm.com",
  lucid: "lucidmotors.com",
  rivian: "rivian.com",
  "bank of montreal": "bmo.com",
  bmo: "bmo.com",
  "hewlett packard enterprise": "hpe.com",
  hpe: "hpe.com",
};

function resolveDomain(company: string, companyDomain?: string | null): string | null {
  const norm = company.toLowerCase().trim();
  if (KNOWN_DOMAINS[norm]) return KNOWN_DOMAINS[norm];

  const cleaned = norm
    .replace(/\b(?:inc\.?|llc\.?|corp\.?|corporation|technologies|technology|group|holdings|co\.?|ltd\.?)\b/g, "")
    .replace(/[^a-z0-9]/g, "")
    .trim();

  if (KNOWN_DOMAINS[cleaned]) return KNOWN_DOMAINS[cleaned];

  if (companyDomain && companyDomain.includes(".")) {
    return companyDomain.replace(/^https?:\/\//, "").replace(/\/.*$/, "").toLowerCase();
  }

  return null;
}

function getLogoUrl(domain: string): string {
  return `https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://${encodeURIComponent(domain)}&size=128`;
}

interface CompanyAvatarProps {
  company: string;
  companyDomain?: string | null;
  size?: "md" | "lg";
}

/**
 * Company avatar showing the official company logo, with graceful
 * fallback to stylized initials if the logo is unavailable.
 */
export default function CompanyAvatar({ company, companyDomain, size = "md" }: CompanyAvatarProps) {
  const [failedDomain, setFailedDomain] = useState<string | null>(null);
  const domain = resolveDomain(company, companyDomain);
  const isFailed = domain ? failedDomain === domain : true;
  const logoUrl = domain && !isFailed ? getLogoUrl(domain) : null;

  const initials = company
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");

  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-sm border border-outline-variant bg-surface-container-lowest dark:bg-surface-container-high",
        "flex items-center justify-center shrink-0 overflow-hidden select-none transition-colors",
        size === "lg" ? "w-12 h-12 p-1.5" : "w-10 h-10 p-1",
      )}
    >
      {logoUrl ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={logoUrl}
          alt=""
          loading="lazy"
          onError={() => {
            if (domain) setFailedDomain(domain);
          }}
          className="w-full h-full object-contain rounded-xs"
        />
      ) : (
        <span className={cn("font-sans font-semibold text-primary", size === "lg" ? "text-title-medium" : "text-title-small")}>
          {initials || "?"}
        </span>
      )}
    </div>
  );
}
