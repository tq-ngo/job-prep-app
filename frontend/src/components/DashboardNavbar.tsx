"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, LogOut, Menu, Newspaper, SlidersHorizontal, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useDismiss } from "@/hooks/useDismiss";
import { cn } from "./ui/cn";
import { ButtonLink } from "./ui/Button";
import SkillsEditor from "./SkillsEditor";
import ThemeToggle from "./ThemeToggle";

const navItems = [
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/news", label: "News", icon: Newspaper },
];

export default function DashboardNavbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  const menuContainerRef = useRef<HTMLDivElement>(null);
  const menuTriggerRef = useRef<HTMLButtonElement>(null);
  const skillsContainerRef = useRef<HTMLDivElement>(null);
  const skillsTriggerRef = useRef<HTMLButtonElement>(null);

  useDismiss(menuOpen, () => setMenuOpen(false), menuContainerRef, menuTriggerRef);
  useDismiss(skillsOpen, () => setSkillsOpen(false), skillsContainerRef, skillsTriggerRef);

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
  const skillCount = user?.skills?.length ?? 0;

  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      setMenuOpen(false);
      setSkillsOpen(false);
      await logout();
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <header
      ref={menuContainerRef}
      className="sticky top-0 z-40 h-14 bg-surface/95 backdrop-blur-md border-b border-outline-variant"
    >
      <div className="max-w-app mx-auto h-full px-4 sm:px-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-6 min-w-0">
          <Link
            href="/"
            className="text-title-large font-semibold tracking-tight text-on-surface hover:text-primary transition-colors shrink-0"
          >
            JobPrep
          </Link>

          <nav aria-label="Main" className="hidden md:flex items-center gap-1">
            {navItems.map(({ href, label, icon: Icon }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex items-center gap-2 h-9 px-4 rounded-full text-label-large font-medium transition-colors",
                    active
                      ? "bg-primary-container text-on-primary-container"
                      : "text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8",
                  )}
                >
                  <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {user ? (
            <div className="hidden lg:flex items-center gap-2">
              <div ref={skillsContainerRef} className="relative">
                <button
                  ref={skillsTriggerRef}
                  type="button"
                  onClick={() => setSkillsOpen((v) => !v)}
                  aria-expanded={skillsOpen}
                  aria-controls="skills-popover"
                  className={cn(
                    "inline-flex items-center gap-2 h-9 px-3.5 rounded-full text-label-large font-medium border transition-colors cursor-pointer",
                    skillsOpen || skillCount > 0
                      ? "bg-primary-container text-on-primary-container border-primary/30"
                      : "bg-surface text-on-surface-variant border-outline-variant hover:text-on-surface hover:bg-on-surface/8",
                  )}
                >
                  <SlidersHorizontal size={16} strokeWidth={1.5} aria-hidden="true" />
                  <span>Skills</span>
                  <span className="font-mono text-label-small tabular-nums px-1.5 py-0.5 rounded-xs bg-surface/75 text-on-surface">
                    {skillCount}
                  </span>
                </button>

                {skillsOpen && (
                  <div
                    id="skills-popover"
                    role="region"
                    aria-label="Tracked skills"
                    className="absolute right-0 mt-2 w-80 rounded-lg bg-surface border border-outline-variant shadow-level-2 dark:shadow-none p-4 z-50"
                  >
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <div>
                        <h2 className="text-title-small font-semibold text-on-surface">Tracked skills</h2>
                        <p className="text-body-small text-on-surface-variant">
                          Used to tailor live job alerts.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSkillsOpen(false)}
                        aria-label="Close skills editor"
                        className="w-7 h-7 inline-flex items-center justify-center rounded-full text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 transition-colors cursor-pointer"
                      >
                        <X size={16} strokeWidth={1.5} aria-hidden="true" />
                      </button>
                    </div>
                    <SkillsEditor autoFocus />
                  </div>
                )}
              </div>

              <span
                title={user.email}
                className="max-w-48 truncate px-3 py-1 rounded-full bg-surface-container-low text-label-medium text-on-surface-variant"
              >
                {user.email}
              </span>

              <button
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
                aria-busy={signingOut || undefined}
                aria-label="Sign out"
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full text-label-large font-medium text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                <LogOut size={16} strokeWidth={1.5} aria-hidden="true" />
                <span>{signingOut ? "Signing out…" : "Sign out"}</span>
              </button>
            </div>
          ) : (
            <div className="hidden lg:flex items-center gap-2">
              <ButtonLink href="/login" variant="filled" size="sm">
                Sign in
              </ButtonLink>
            </div>
          )}

          <ThemeToggle />

          <button
            ref={menuTriggerRef}
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-controls="app-menu"
            aria-label="Menu"
            className="lg:hidden w-10 h-10 inline-flex items-center justify-center rounded-full text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 transition-colors cursor-pointer"
          >
            {menuOpen ? <X size={18} strokeWidth={1.5} aria-hidden="true" /> : <Menu size={18} strokeWidth={1.5} aria-hidden="true" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <div
          id="app-menu"
          className="lg:hidden border-b border-outline-variant bg-surface shadow-level-2 dark:shadow-none px-4 py-4 space-y-4"
        >
          <nav aria-label="Main menu" className="md:hidden flex flex-col gap-1">
            {navItems.map(({ href, label, icon: Icon }) => {
              const active = isActive(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMenuOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-2.5 rounded-sm text-body-medium font-medium transition-colors",
                    active
                      ? "bg-primary-container text-on-primary-container"
                      : "text-on-surface hover:bg-on-surface/8",
                  )}
                >
                  <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>

          {user ? (
            <div className="space-y-4 md:pt-0 pt-3 border-t md:border-t-0 border-outline-variant">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h2 className="text-label-large font-semibold text-on-surface">Tracked skills</h2>
                  <span className="font-mono text-label-small text-on-surface-variant tabular-nums">
                    {skillCount} tracked
                  </span>
                </div>
                <SkillsEditor />
              </div>

              <div className="flex items-center justify-between gap-3 pt-3 border-t border-outline-variant">
                <span className="text-body-small text-on-surface-variant truncate">{user.email}</span>
                <button
                  type="button"
                  onClick={handleSignOut}
                  disabled={signingOut}
                  aria-busy={signingOut || undefined}
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full text-label-large font-medium text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer shrink-0"
                >
                  <LogOut size={16} strokeWidth={1.5} aria-hidden="true" />
                  <span>{signingOut ? "Signing out…" : "Sign out"}</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="pt-3 border-t border-outline-variant">
              <ButtonLink href="/login" variant="filled" onClick={() => setMenuOpen(false)} className="w-full">
                Sign in
              </ButtonLink>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
