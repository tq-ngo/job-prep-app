"use client";

import { ArrowRight } from "lucide-react";
import { ButtonLink } from "@/components/ui/Button";
import { useSessionHint } from "@/hooks/useSessionHint";

export function MarketingHeaderActions() {
  const signedIn = useSessionHint();

  if (signedIn) {
    return (
      <div className="hidden md:flex items-center gap-2">
        <ButtonLink href="/news" variant="text" size="sm">
          Tech news
        </ButtonLink>
        <ButtonLink href="/jobs" variant="filled" size="sm">
          Open Job Board
        </ButtonLink>
      </div>
    );
  }

  return (
    <div className="hidden md:flex items-center gap-2">
      <ButtonLink href="/login" variant="text" size="sm">
        Sign in
      </ButtonLink>
      <ButtonLink href="/register" variant="filled" size="sm">
        Get started
      </ButtonLink>
    </div>
  );
}

export function MarketingMobileAuthActions({ onNavigate }: { onNavigate: () => void }) {
  const signedIn = useSessionHint();

  if (signedIn) {
    return (
      <div className="flex flex-col gap-2 pt-3 border-t border-outline-variant">
        <ButtonLink href="/jobs" variant="filled" onClick={onNavigate}>
          Open Job Board
        </ButtonLink>
        <ButtonLink href="/news" variant="outlined" onClick={onNavigate}>
          Tech News Radar
        </ButtonLink>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 pt-3 border-t border-outline-variant">
      <ButtonLink href="/register" variant="filled" onClick={onNavigate}>
        Get started
      </ButtonLink>
      <ButtonLink href="/login" variant="outlined" onClick={onNavigate}>
        Sign in
      </ButtonLink>
    </div>
  );
}

export function MarketingHeroActions({ primaryLabel = "Create free account" }: { primaryLabel?: string }) {
  const signedIn = useSessionHint();

  if (signedIn) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <ButtonLink href="/jobs" variant="filled" size="lg">
          Open Job Board
          <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
        </ButtonLink>
        <ButtonLink href="/news" variant="outlined" size="lg">
          Tech News Radar
        </ButtonLink>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <ButtonLink href="/register" variant="filled" size="lg">
        {primaryLabel}
        <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
      </ButtonLink>
      <ButtonLink href="/login" variant="outlined" size="lg">
        Sign in
      </ButtonLink>
    </div>
  );
}
