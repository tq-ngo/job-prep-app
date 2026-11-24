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
export default function MarketingMobileNav({ isLoggedIn = false }: { isLoggedIn?: boolean }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useDismiss(open, close, containerRef, triggerRef);

  const links = isLoggedIn
    ? [
        { href: "/jobs", label: "Job Board" },
        { href: "/news", label: "Tech Radar" },
        { href: "/#features", label: "Features" },
        { href: "/#demo", label: "AI Intelligence" },
      ]
    : LINKS;

  return (
    <div ref={containerRef} className="md:hidden">
      <Button
        ref={triggerRef}
        variant="text"
        size="icon"
        aria-label="Menu"
        aria-expanded={open}
        aria-controls="marketing-menu"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
      </Button>
      {open && (
        <nav id="marketing-menu" aria-label="Main menu" className="absolute inset-x-0 top-16 border-b border-outline-variant bg-surface-container-low/95 backdrop-blur-md rounded-b-lg px-6 py-4 shadow-level-3">
          <ul className="space-y-1">
            {links.map(({ href, label }) => (
              <li key={href}>
                <Link href={href} onClick={close} className="block rounded-full px-4 py-2.5 text-label-large font-medium text-on-surface-variant hover:bg-on-surface/8 hover:text-on-surface focus-visible:bg-on-surface/12 transition-colors">
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
