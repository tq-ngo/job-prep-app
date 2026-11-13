"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, LogIn, LogOut, Menu, Newspaper, Sparkles, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useDismiss } from "@/hooks/useDismiss";
import SkillsEditor from "@/components/SkillsEditor";
import ThemeToggle from "@/components/ThemeToggle";
import Badge from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import Skeleton from "@/components/ui/Skeleton";

const NAV_LINKS = [
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/news", label: "News", icon: Newspaper },
];
const PREVIEW_SKILLS = 5;

/** Desktop: up to five skills, plus a popover to edit the full list. */
function SkillsSummary() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useDismiss(open, close, containerRef, triggerRef);

  const skills = user?.skills ?? [];
  return (
    <div ref={containerRef} className="relative hidden lg:flex items-center gap-2 min-w-0">
      <span className="font-mono text-2xs text-foreground-subtle uppercase tracking-wider shrink-0 flex items-center gap-1">
        <Sparkles size={11} aria-hidden="true" className="text-spruce-green" /> Skills:
      </span>
      <ul aria-label="Tracked skills" className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
        {skills.slice(0, PREVIEW_SKILLS).map((skill) => (
          <li key={skill}>
            <Badge variant="skill">{skill}</Badge>
          </li>
        ))}
        {skills.length > PREVIEW_SKILLS && (
          <li className="font-mono text-2xs text-foreground-subtle shrink-0">+{skills.length - PREVIEW_SKILLS}</li>
        )}
      </ul>
      <Button
        ref={triggerRef}
        variant="secondary"
        size="xs"
        aria-expanded={open}
        aria-controls="skills-popover"
        onClick={() => setOpen((o) => !o)}
        className="shrink-0 font-mono rounded-full"
      >
        {skills.length ? "Edit" : "Add skills"}
      </Button>

      {open && (
        <div
          id="skills-popover"
          role="group"
          aria-label="Edit tracked skills"
          className="absolute left-0 top-full mt-2 w-80 rounded-card border border-slate-soft bg-neutral-soft p-4 shadow-pop"
        >
          <SkillsEditor autoFocus />
        </div>
      )}
    </div>
  );
}

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
    <header ref={headerRef} className="sticky top-0 z-40 w-full bg-background/90 backdrop-blur-md border-b border-slate-soft transition-colors duration-200">
      <div className="max-w-app mx-auto px-4 sm:px-6 lg:px-8 h-12 flex items-center justify-between gap-4">
        <div className="flex items-center gap-6 min-w-0">
          <Link href="/" className="font-serif text-xl font-medium tracking-tight text-slate-ink hover:text-spruce-green transition-colors">
            JobPrep
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-1.5">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-150",
                  isActive(href)
                    ? "bg-spruce-green/10 text-spruce-green font-semibold shadow-xs"
                    : "text-foreground-muted hover:text-slate-ink hover:bg-neutral-soft",
                )}
              >
                <Icon size={14} aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>

          {user && <SkillsSummary />}
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <ThemeToggle />

          {isLoading ? (
            // Session unknown (server couldn't resolve it): a neutral
            // placeholder, never a "Sign In" button that then flips.
            <Skeleton className="w-40 h-6" />
          ) : user ? (
            <div className="flex items-center gap-2 pl-2.5 py-0.5 pr-1 border border-slate-soft rounded-full bg-neutral-soft/80">
              <span className="hidden sm:inline font-sans text-xs text-foreground-muted truncate max-w-40" title={user.email}>
                {user.email}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={logout}
                title="Sign out"
                aria-label="Sign out"
                className="h-7 w-7 rounded-full text-foreground-subtle hover:text-slate-ink hover:bg-surface-container"
              >
                <LogOut size={14} aria-hidden="true" />
              </Button>
            </div>
          ) : (
            <ButtonLink href="/login" size="sm" icon={<LogIn size={13} aria-hidden="true" />}>
              Sign In
            </ButtonLink>
          )}

          {/* Below lg, where the skills summary is hidden; it used to appear
              only below md, so md–lg had neither skills nor a menu. */}
          <Button
            ref={menuButtonRef}
            variant="ghost"
            size="icon"
            className="lg:hidden rounded-full"
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
        <div id="app-menu" className="lg:hidden border-t border-slate-soft px-4 py-3 bg-neutral-soft/95 backdrop-blur-md shadow-card space-y-3">
          <nav aria-label="Main menu" className="md:hidden space-y-1">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={closeMenu}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 px-3.5 py-2 rounded-full text-sm font-medium transition-colors",
                  isActive(href) ? "bg-spruce-green/10 text-spruce-green font-semibold" : "text-foreground-muted hover:bg-surface-container",
                )}
              >
                <Icon size={16} aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
          {user && (
            <section aria-labelledby="menu-skills-heading" className="md:border-t-0 border-t border-slate-soft pt-3 md:pt-0">
              <h2 id="menu-skills-heading" className="text-xs text-foreground-subtle font-mono uppercase tracking-wider mb-2">
                Tracked skills
              </h2>
              <SkillsEditor />
            </section>
          )}
        </div>
      )}
    </header>
  );
}
