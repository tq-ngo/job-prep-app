"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useDismiss } from "@/hooks/useDismiss";
import { Button } from "@/components/ui/Button";

const LINKS = [
  { href: "/#features", label: "Features" },
  { href: "/#demo", label: "AI Intelligence" },
  { href: "/news", label: "Tech Radar" },
  { href: "/jobs", label: "Job Board" },
  { href: "/login", label: "Sign In" },
];

/** The header's links below md, where they used to be hidden with no menu. */
export default function MarketingMobileNav() {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useDismiss(open, close, containerRef, triggerRef);

  return (
    <div ref={containerRef} className="md:hidden">
      <Button
        ref={triggerRef}
        variant="ghost"
        size="icon"
        aria-label="Menu"
        aria-expanded={open}
        aria-controls="marketing-menu"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
      </Button>
      {open && (
        <nav id="marketing-menu" aria-label="Main menu" className="absolute inset-x-0 top-16 border-b border-slate-soft bg-background px-6 py-3 shadow-pop">
          <ul className="space-y-1">
            {LINKS.map(({ href, label }) => (
              <li key={href}>
                <Link href={href} onClick={close} className="block rounded-control px-3 py-2 text-sm font-medium text-foreground-muted hover:bg-slate-soft/30 hover:text-slate-ink">
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
