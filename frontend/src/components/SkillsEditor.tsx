"use client";

import { useState, type FormEvent } from "react";
import { Plus, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { authApi } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";

export default function SkillsEditor({ autoFocus = false }: { autoFocus?: boolean }) {
  const { user, refreshUser } = useAuth();
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const skills = user?.skills ?? [];

  const persist = async (next: string[]) => {
    setSaving(true);
    setError(null);
    try {
      await authApi.updateSkills(next);
      await refreshUser();
    } catch (err) {
      setError(apiErrorMessage(err, { fallback: "Couldn't save your skills. Please try again." }));
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    const cleaned = input.trim();
    if (!cleaned) return;
    if (skills.some((s) => s.toLowerCase() === cleaned.toLowerCase())) {
      setInput("");
      return;
    }
    const next = [...skills, cleaned];
    setInput("");
    await persist(next);
  };

  const handleRemove = async (skill: string) => {
    await persist(skills.filter((s) => s !== skill));
  };

  return (
    <div className="space-y-3">
      <form onSubmit={handleAdd} className="flex items-center gap-2">
        <Input
          type="text"
          name="skillInput"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add a skill (e.g. Python)"
          aria-label="Add a skill"
          autoFocus={autoFocus}
          disabled={saving}
          className="flex-1"
          inputClassName="h-9 text-body-small"
        />
        <Button type="submit" variant="tonal" size="sm" disabled={saving || !input.trim()} loading={saving}>
          <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
          <span>Add</span>
        </Button>
      </form>

      {error && (
        <p role="alert" className="text-body-small text-error">
          {error}
        </p>
      )}

      {skills.length > 0 ? (
        <ul aria-label="Tracked skills list" className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <li
              key={skill}
              className="inline-flex items-center gap-1 pl-2.5 pr-1 py-0.5 rounded-xs bg-surface-container-low border border-outline-variant font-mono text-label-small text-on-surface"
            >
              <span>{skill}</span>
              <button
                type="button"
                onClick={() => handleRemove(skill)}
                disabled={saving}
                aria-label={`Remove ${skill}`}
                className="w-6 h-6 inline-flex items-center justify-center rounded-xs text-on-surface-variant hover:text-on-surface hover:bg-on-surface/8 disabled:opacity-50 transition-colors cursor-pointer"
              >
                <X size={12} strokeWidth={1.5} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body-small text-on-surface-variant">
          No skills tracked yet. Add languages or frameworks to prioritize alerts.
        </p>
      )}
    </div>
  );
}
