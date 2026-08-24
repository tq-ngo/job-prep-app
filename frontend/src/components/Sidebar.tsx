"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, Newspaper, LogOut, LogIn, X, Plus, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { authApi } from "@/lib/api";
import { useState } from "react";

export default function Sidebar() {
  const { user, logout, refreshUser } = useAuth();
  const pathname = usePathname();
  const [isEditingSkills, setIsEditingSkills] = useState(false);
  const [skillInput, setSkillInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);

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
      // Silently fail — user can retry
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
    <aside className="w-64 fixed inset-y-0 left-0 bg-background flex flex-col z-40 border-r border-slate-soft transition-colors duration-300">
      {/* Logo */}
      <div className="p-8 border-b border-slate-soft">
        <Link href="/jobs" className="font-serif text-2xl font-semibold text-slate-ink hover:text-spruce-green transition-colors">
          JobPrep
        </Link>
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 px-4 py-8 space-y-2">
        {navLinks.map(({ href, label, icon: Icon }) => {
          const isActive = pathname.startsWith(href);
          return (
            <Link 
              key={href}
              href={href} 
              className={`flex items-center gap-3 px-4 py-3 rounded-md transition-colors font-sans text-sm font-medium group ${
                isActive 
                  ? "bg-spruce-green/10 text-spruce-green" 
                  : "text-foreground hover:bg-slate-soft/30 hover:text-spruce-green"
              }`}
            >
              <Icon size={18} className={`transition-colors ${isActive ? "text-spruce-green" : "text-slate-ink/70 group-hover:text-spruce-green"}`} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User Skills Section */}
      {user && user.skills && user.skills.length > 0 && (
        <div className="px-6 pb-4">
          <div className="flex items-center justify-between mb-2">
            <p className="font-mono text-[10px] text-slate-ink/40 uppercase tracking-widest">Tracked Skills</p>
            <button 
              onClick={() => setIsEditingSkills(!isEditingSkills)}
              className="text-slate-ink/30 hover:text-spruce-green transition-colors"
            >
              {isEditingSkills ? <X size={12} /> : <Plus size={12} />}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {user.skills.map((skill) => (
              <span 
                key={skill} 
                className="group inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-spruce-green/10 text-spruce-green font-mono text-[10px] uppercase tracking-wider"
              >
                {skill}
                {isEditingSkills && (
                  <button 
                    onClick={() => handleRemoveSkill(skill)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X size={8} />
                  </button>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Inline skill editor */}
      {isEditingSkills && user && (
        <div className="px-6 pb-4">
          <div className="flex gap-1.5">
            <input
              type="text"
              value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              onKeyDown={handleSkillKeyDown}
              placeholder="Add skill..."
              className="flex-1 bg-background border border-slate-soft rounded px-2.5 py-1.5 text-xs text-slate-ink focus:outline-none focus:ring-1 focus:ring-spruce-green transition-all font-mono"
              autoFocus
            />
            <button
              onClick={handleAddSkill}
              disabled={!skillInput.trim() || isSaving}
              className="px-2.5 py-1.5 bg-spruce-green hover:bg-spruce-green-hover disabled:bg-slate-soft text-warm-ivory rounded text-xs font-medium transition-colors"
            >
              {isSaving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            </button>
          </div>
        </div>
      )}

      {/* User Section */}
      <div className="p-6 border-t border-slate-soft">
        {user ? (
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="font-sans text-sm text-slate-ink font-medium truncate" title={user.email}>
                {user.email}
              </p>
              {(!user.skills || user.skills.length === 0) && (
                <button 
                  onClick={() => setIsEditingSkills(true)}
                  className="font-mono text-[10px] text-spruce-green/60 hover:text-spruce-green transition-colors uppercase tracking-widest"
                >
                  + Add skills
                </button>
              )}
            </div>
            <button 
              onClick={logout}
              className="text-slate-ink/40 hover:text-amber-clay transition-colors shrink-0 ml-3"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <Link 
            href="/login"
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded bg-spruce-green/10 text-spruce-green hover:bg-spruce-green/20 transition-colors font-sans text-sm font-medium"
          >
            <LogIn size={14} /> Sign In
          </Link>
        )}
      </div>
    </aside>
  );
}
