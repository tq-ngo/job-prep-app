"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { authApi, type User } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { ME_QUERY_KEY, useAuth } from "@/context/AuthContext";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import Field from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";

// Mirror the API's limits (schemas/user.py) so mistakes are caught here,
// with a specific message, instead of as a generic 422.
const MAX_SKILLS = 30;
const MAX_SKILL_LENGTH = 40;

/**
 * Add and remove tracked skills (live job alerts are matched against them).
 * Shared by the desktop popover and the mobile menu.
 *
 * Saves are optimistic: the change shows at once, and is rolled back with an
 * error if the server rejects it. Saves used to fail silently, leaving the
 * list showing a change that hadn't been stored.
 */
export default function SkillsEditor({ autoFocus = false }: { autoFocus?: boolean }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const skills = user?.skills ?? [];

  const save = async (next: string[]) => {
    const previous = queryClient.getQueryData<User | null>(ME_QUERY_KEY);
    if (!previous) return false;
    setError(null);
    setSaving(true);
    queryClient.setQueryData<User>(ME_QUERY_KEY, { ...previous, skills: next });
    try {
      // The server normalizes (lowercases, de-duplicates); keep its version.
      queryClient.setQueryData(ME_QUERY_KEY, await authApi.updateSkills(next));
      return true;
    } catch (err) {
      queryClient.setQueryData(ME_QUERY_KEY, previous);
      setError(apiErrorMessage(err, { fallback: "Couldn't save your skills. Try again." }));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const skill = input.trim();
    if (!skill) return;
    if (skill.length > MAX_SKILL_LENGTH) return setError(`Skills can be at most ${MAX_SKILL_LENGTH} characters.`);
    if (skills.some((s) => s.toLowerCase() === skill.toLowerCase())) return setError(`“${skill}” is already in your list.`);
    if (skills.length >= MAX_SKILLS) return setError(`You can track up to ${MAX_SKILLS} skills.`);
    if (await save([...skills, skill])) setInput("");
  };

  return (
    <div>
      {skills.length > 0 ? (
        <ul aria-label="Tracked skills" className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <li key={skill}>
              <Badge variant="skill" className="pr-0.5">
                {skill}
                {/* 24px target (WCAG 2.5.8), pulled into the badge's line height. */}
                <button
                  type="button"
                  onClick={() => save(skills.filter((s) => s !== skill))}
                  disabled={saving}
                  aria-label={`Remove ${skill}`}
                  className="-my-1 inline-flex h-6 w-6 items-center justify-center rounded-control hover:bg-spruce-green/15 disabled:cursor-not-allowed"
                >
                  <X size={11} aria-hidden="true" />
                </button>
              </Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-foreground-muted">No skills yet. Add the technologies you want job alerts for.</p>
      )}

      <form onSubmit={handleAdd} className="mt-3 flex gap-2 items-start">
        <Field label="Add a skill" labelVisible={false} className="flex-1">
          <Input
            size="sm"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setError(null);
            }}
            placeholder="Add a skill, e.g. React"
            autoFocus={autoFocus}
            maxLength={MAX_SKILL_LENGTH + 10}
          />
        </Field>
        <Button type="submit" size="sm" variant="secondary" loading={saving} icon={<Plus size={13} aria-hidden="true" />}>
          Add
        </Button>
      </form>
      {error && (
        <p role="alert" className="mt-2 text-xs font-medium text-amber-clay">
          {error}
        </p>
      )}
    </div>
  );
}
