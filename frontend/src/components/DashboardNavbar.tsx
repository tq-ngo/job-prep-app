"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, Newspaper, LogOut, LogIn, X, Plus, Loader2, Sparkles, Menu } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { authApi } from "@/lib/api";
import { useState } from "react";
import ThemeToggle from "@/components/ThemeToggle";

export default function DashboardNavbar() {
  const { user, logout, refreshUser } = useAuth();
  const pathname = usePathname();
  const [isEditingSkills, setIsEditingSkills] = useState(false);
  const [skillInput, setSkillInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { href: "/jobs", label: "Jobs", icon: Briefcase },
    { href: "/news", label: "News", icon: Newspaper },
  ];

  const handleAddSkill = async () => {
    if (!skillInput.trim() || !user) return;
    const updated = [...(user.skills || []), skillInput.trim()];
    setIsSaving(true);
    try {
      await authApi.updateSkills(updated);
      await refreshUser();
      setSkillInput("");
    } catch {
      // Silently fail
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveSkill = async (skill: string) => {
    if (!user) return;
    const updated = user.skills.filter((s) => s !== skill);
    setIsSaving(true);
    try {
      await authApi.updateSkills(updated);
      await refreshUser();
    } catch {
      // Silently fail
    } finally {
      setIsSaving(false);
    }
  };

  const handleSkillKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddSkill();
    }
    if (e.key === "Escape") {
      setIsEditingSkills(false);
      setSkillInput("");
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-background/90 backdrop-blur-md border-b border-slate-soft transition-colors duration-200">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
        
        {/* Brand Logo & Main Nav */}
        <div className="flex items-center gap-6">
          <Link
            href="/"
            className="font-serif text-xl font-medium tracking-tight text-slate-ink hover:text-spruce-green transition-colors flex items-center gap-2"
          >
            <span>JobPrep</span>
          </Link>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map(({ href, label, icon: Icon }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-spruce-green/10 text-spruce-green font-semibold"
                      : "text-foreground-muted hover:text-slate-ink hover:bg-slate-soft/30"
                  }`}
                >
                  <Icon size={14} className={isActive ? "text-spruce-green" : "text-foreground-subtle"} />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Center: Tracked Skills Pills (Compact View) */}
        {user && (
          <div className="hidden lg:flex items-center gap-2 max-w-md overflow-hidden">
            <span className="font-mono text-[10px] text-foreground-subtle uppercase tracking-wider shrink-0 flex items-center gap-1">
              <Sparkles size={11} className="text-spruce-green" /> Skills:
            </span>
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
              {(user.skills || []).slice(0, 5).map((skill) => (
                <span
                  key={skill}
                  className="group inline-flex items-center gap-1 px-2 py-0.5 rounded bg-neutral-soft border border-slate-soft text-spruce-green font-mono text-[10px] uppercase tracking-wider shrink-0"
                >
                  {skill}
                  {isEditingSkills && (
                    <button
                      onClick={() => handleRemoveSkill(skill)}
                      className="text-foreground-subtle hover:text-amber-clay ml-0.5"
                    >
                      <X size={8} />
                    </button>
                  )}
                </span>
              ))}
              {(user.skills || []).length > 5 && (
                <span className="font-mono text-[10px] text-foreground-subtle shrink-0">
                  +{(user.skills || []).length - 5}
                </span>
              )}
              {isEditingSkills ? (
                <div className="flex items-center gap-1 shrink-0">
                  <input
                    type="text"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={handleSkillKeyDown}
                    placeholder="New skill..."
                    className="w-24 bg-background border border-slate-soft rounded px-1.5 py-0.5 text-[10px] text-slate-ink focus:outline-none focus:ring-1 focus:ring-spruce-green font-mono"
                    autoFocus
                  />
                  <button
                    onClick={handleAddSkill}
                    disabled={!skillInput.trim() || isSaving}
                    className="p-1 bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory rounded text-[10px]"
                  >
                    {isSaving ? <Loader2 size={10} className="animate-spin" /> : <Plus size={10} />}
                  </button>
                  <button
                    onClick={() => setIsEditingSkills(false)}
                    className="text-foreground-subtle hover:text-slate-ink p-1"
                  >
                    <X size={10} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setIsEditingSkills(true)}
                  className="font-mono text-[10px] text-foreground-subtle hover:text-spruce-green border border-dashed border-slate-soft hover:border-spruce-green/50 rounded px-1.5 py-0.5 shrink-0 transition-colors"
                >
                  + Edit
                </button>
              )}
            </div>
          </div>
        )}

        {/* Right Side Actions: Theme Switch + User Account */}
        <div className="flex items-center gap-3">
          <ThemeToggle />

          {user ? (
            <div className="flex items-center gap-3 pl-2 border-l border-slate-soft">
              <span
                className="hidden sm:inline font-sans text-xs text-foreground-muted truncate max-w-[160px]"
                title={user.email}
              >
                {user.email}
              </span>
              <button
                onClick={logout}
                className="p-1.5 rounded text-foreground-subtle hover:text-amber-clay hover:bg-slate-soft/30 transition-colors"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-spruce-green hover:bg-spruce-green-hover text-warm-ivory text-xs font-medium transition-colors"
            >
              <LogIn size={13} /> Sign In
            </Link>
          )}

          {/* Mobile hamburger menu toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-1.5 text-foreground-subtle hover:text-slate-ink"
            aria-label="Toggle mobile menu"
          >
            <Menu size={18} />
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-soft px-4 py-3 bg-background space-y-2">
          {navLinks.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileMenuOpen(false)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded text-sm font-medium ${
                pathname.startsWith(href)
                  ? "bg-spruce-green/10 text-spruce-green"
                  : "text-foreground-muted hover:bg-slate-soft/30"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
          {user && (
            <div className="pt-2 border-t border-slate-soft">
              <p className="text-xs text-foreground-subtle font-mono mb-2">Tracked Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {(user.skills || []).map((skill) => (
                  <span
                    key={skill}
                    className="px-2 py-0.5 rounded bg-neutral-soft border border-slate-soft text-spruce-green font-mono text-[10px] uppercase"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
