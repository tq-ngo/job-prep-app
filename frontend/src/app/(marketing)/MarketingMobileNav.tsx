"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { ButtonLink } from "@/components/ui/Button";
import { useDismiss } from "@/hooks/useDismiss";

interface Props {
  links: { href: string; label: string }[];
}

export default function MarketingMobileNav({ links }: Props) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useDismiss(open, () => setOpen(false), containerRef, triggerRef);

  return (
    <div ref={containerRef} className="md:hidden">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="marketing-mobile-menu"
        aria-label={open ? "Close menu" : "Open menu"}
        className="w-10 h-10 inline-flex items-center justify-center rounded-full text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 transition-colors cursor-pointer"
      >
        {open ? <X size={18} strokeWidth={1.5} aria-hidden="true" /> : <Menu size={18} strokeWidth={1.5} aria-hidden="true" />}
      </button>

      {open && (
        <div
          id="marketing-mobile-menu"
          className="fixed inset-x-0 top-14 bg-surface border-b border-outline-variant shadow-level-2 dark:shadow-none px-4 py-4 space-y-4 z-50"
        >
          <nav aria-label="Mobile" className="flex flex-col gap-1">
            {links.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className="px-3 py-2.5 rounded-sm text-body-medium font-medium text-on-surface hover:bg-on-surface/8 transition-colors"
              >
                {label}
              </Link>
            ))}
          </nav>

          <div className="flex flex-col gap-2 pt-3 border-t border-outline-variant">
            <ButtonLink href="/register" variant="filled" onClick={() => setOpen(false)}>
              Get started
            </ButtonLink>
            <ButtonLink href="/login" variant="outlined" onClick={() => setOpen(false)}>
              Sign in
            </ButtonLink>
          </div>
        </div>
      )}
    </div>
  );
}
