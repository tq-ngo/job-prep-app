"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, LogIn, LogOut, Menu, Newspaper, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useDismiss } from "@/hooks/useDismiss";
import ThemeToggle from "@/components/ThemeToggle";
import { Button, ButtonLink } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import Skeleton from "@/components/ui/Skeleton";

const NAV_LINKS = [
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/news", label: "News", icon: Newspaper },
];

export default function DashboardNavbar() {
  const { user, isLoading, logout } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const headerRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  useDismiss(menuOpen, closeMenu, headerRef, menuButtonRef);

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header ref={headerRef} className="sticky top-0 z-40 w-full bg-surface/95 backdrop-blur-md border-b border-outline-variant transition-colors duration-200">
      <div className="w-full px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between gap-4">
        <div className="flex items-center gap-6 min-w-0">
          <Link href="/" className="font-serif text-title-large font-medium tracking-tight text-on-surface hover:text-primary transition-colors">
            JobPrep
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-1.5">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 px-4 py-1.5 rounded-full text-label-medium transition-all duration-150",
                  isActive(href)
                    ? "bg-secondary-container text-on-secondary-container font-semibold"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 focus-visible:bg-on-surface/12 font-medium",
                )}
              >
                <Icon size={14} aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <ThemeToggle />

          {isLoading ? (
            // Session unknown (server couldn't resolve it): a neutral
            // placeholder, never a "Sign In" button that then flips.
            <Skeleton className="w-40 h-6 rounded-full" />
          ) : user ? (
            <div className="flex items-center gap-2 pl-3 py-0.5 pr-1 border border-outline-variant rounded-full bg-surface-container-low">
              <span className="hidden sm:inline font-sans text-label-medium text-on-surface-variant truncate max-w-40" title={user.email}>
                {user.email}
              </span>
              <Button
                variant="text"
                size="icon"
                onClick={logout}
                title="Sign out"
                aria-label="Sign out"
                className="h-7 w-7 text-on-surface-variant hover:text-on-surface"
              >
                <LogOut size={14} aria-hidden="true" />
              </Button>
            </div>
          ) : (
            <ButtonLink href="/login" variant="filled" size="sm" icon={<LogIn size={13} aria-hidden="true" />}>
              Sign In
            </ButtonLink>
          )}

          {/* Below lg, where the skills summary is hidden; it used to appear
              only below md, so md–lg had neither skills nor a menu. */}
          <Button
            ref={menuButtonRef}
            variant="text"
            size="icon"
            className="lg:hidden"
            aria-label="Menu"
            aria-expanded={menuOpen}
            aria-controls="app-menu"
            onClick={() => setMenuOpen((o) => !o)}
          >
            {menuOpen ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
          </Button>
        </div>
      </div>

      {menuOpen && (
        <div id="app-menu" className="lg:hidden border-t border-outline-variant px-4 py-3 bg-surface-container-low shadow-level-2 space-y-3">
          <nav aria-label="Main menu" className="md:hidden space-y-1">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={closeMenu}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 px-4 py-2 rounded-full text-label-large transition-colors",
                  isActive(href)
                    ? "bg-secondary-container text-on-secondary-container font-semibold"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 focus-visible:bg-on-surface/12 font-medium",
                )}
              >
                <Icon size={16} aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
