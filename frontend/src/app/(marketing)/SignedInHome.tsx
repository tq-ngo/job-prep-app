"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Briefcase, ExternalLink, Newspaper, Search, Sparkles } from "lucide-react";
import type { User } from "@/lib/api";
import type { PublicStats } from "./LandingHero";
import { Button, ButtonLink } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import {
  BentoAIDemoCard,
  BentoPipelineCard,
  BentoSSECard,
  InteractiveLiveCard,
} from "./LandingDemos";

export default function SignedInHome({
  user,
  stats,
}: {
  user: User;
  stats: PublicStats | null;
}) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const name = user.email.split("@")[0] || "there";

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/jobs?q=${encodeURIComponent(searchQuery.trim())}`);
    } else {
      router.push("/jobs");
    }
  };

  const metrics = stats
    ? [
        { value: stats.active_jobs.toLocaleString("en-US"), label: "Open roles" },
        { value: stats.companies.toLocaleString("en-US"), label: "Companies" },
        { value: stats.added_24h.toLocaleString("en-US"), label: "Added in 24h" },
      ]
    : [
        { value: "4", label: "GitHub repos" },
        { value: "6h", label: "Crawl cadence" },
        { value: "768d", label: "Vector search" },
      ];

  return (
    <div className="pt-28 pb-20">
      {/* Top Welcome Section */}
      <section className="max-w-6xl mx-auto px-6 mb-16">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-spruce-green/10 border border-spruce-green/20 mb-5">
              <span className="w-1.5 h-1.5 rounded-full bg-spruce-green animate-pulse" />
              <span className="font-mono text-2xs uppercase tracking-widest text-spruce-green font-semibold">
                Live Command Center · Signed in as {user.email}
              </span>
            </div>

            <h1 className="text-4xl sm:text-5xl font-serif font-medium text-slate-ink leading-[1.15] tracking-tight mb-4">
              Welcome back, <br />
              <span className="text-spruce-green italic">{name}</span>.
            </h1>

            <p className="text-base text-foreground-muted leading-relaxed mb-6 max-w-lg">
              Your personal dashboard is actively tracking internship opportunities across GitHub and LinkedIn with AI skill extraction and live updates.
            </p>

            {/* Quick Search on Homepage */}
            <form onSubmit={handleSearch} className="flex gap-2 max-w-md mb-6">
              <Input
                size="md"
                pill
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search role, company, or skill…"
                leadingIcon={<Search size={16} />}
                className="flex-1 text-sm bg-neutral-soft"
              />
              <Button type="submit" size="md" className="rounded-full px-5">
                Search
              </Button>
            </form>

            {/* Primary Action Buttons */}
            <div className="flex flex-wrap gap-3 mb-8">
              <ButtonLink href="/jobs" size="lg" icon={<Briefcase size={16} />} className="rounded-full shadow-xs">
                Open Job Board <ArrowRight size={15} aria-hidden="true" />
              </ButtonLink>
              <ButtonLink href="/news" variant="secondary" size="lg" icon={<Newspaper size={16} />} className="rounded-full">
                Tech News Radar
              </ButtonLink>
            </div>

            {/* Quick Metrics */}
            <dl className="grid grid-cols-3 gap-6 pt-6 border-t border-slate-soft max-w-md">
              {metrics.map(({ value, label }) => (
                <div key={label} className="flex flex-col-reverse">
                  <dt className="font-mono text-2xs uppercase tracking-wider text-foreground-subtle mt-0.5">{label}</dt>
                  <dd className="text-2xl font-serif font-medium text-slate-ink">{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Right Column: Interactive Live Stream */}
          <div>
            <InteractiveLiveCard />
          </div>
        </div>
      </section>

      {/* Tracked Skills Hub */}
      <section className="max-w-6xl mx-auto px-6 mb-16">
        <Card tone="muted" padding="lg" className="border-slate-soft/80 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-spruce-green" />
                <h2 className="text-lg font-serif font-medium text-slate-ink">Your Tracked Skills</h2>
              </div>
              <p className="text-xs text-foreground-muted mt-0.5">
                Postings matching your tracked technologies are flagged with live alerts.
              </p>
            </div>
            <ButtonLink href="/jobs" variant="secondary" size="sm" className="rounded-full">
              Manage in Navbar
            </ButtonLink>
          </div>

          {user.skills && user.skills.length > 0 ? (
            <div className="flex flex-wrap gap-2 pt-2">
              {user.skills.map((skill) => (
                <Link
                  key={skill}
                  href={`/jobs?skill=${encodeURIComponent(skill)}`}
                  className="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-spruce-green/10 text-spruce-green border border-spruce-green/20 hover:bg-spruce-green/20 transition-colors text-xs font-mono font-medium"
                >
                  <span>{skill}</span>
                  <ExternalLink size={11} className="opacity-60 group-hover:opacity-100 transition-opacity" />
                </Link>
              ))}
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-background border border-dashed border-slate-soft text-center">
              <p className="text-xs text-foreground-muted mb-2">You haven&apos;t added any tracked skills yet.</p>
              <ButtonLink href="/jobs" size="sm" className="rounded-full">
                Add skills in the Job Board
              </ButtonLink>
            </div>
          )}
        </Card>
      </section>

      {/* Live AI Intelligence Demos */}
      <section className="py-14 border-t border-slate-soft bg-neutral-soft/30">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center max-w-xl mx-auto mb-10">
            <span className="font-mono text-2xs uppercase tracking-widest text-spruce-green font-semibold">
              Live Intelligence Engine
            </span>
            <h2 className="text-2xl font-serif font-medium text-slate-ink tracking-tight mt-1.5">
              Automated crawling, extraction, and deduplication.
            </h2>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            <BentoPipelineCard />
            <BentoSSECard initialCount={stats ? stats.added_24h : null} />
            <BentoAIDemoCard />
          </div>
        </div>
      </section>
    </div>
  );
}
