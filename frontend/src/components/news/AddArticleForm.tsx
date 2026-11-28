"use client";

import { useState } from "react";
import { newsApi } from "@/lib/api";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Field from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import Spinner from "@/components/ui/Spinner";
import { useNewsScrape } from "./useNewsScrape";

/** Paste a URL to have it crawled and summarized onto the radar. */
export default function AddArticleForm() {
  const [url, setUrl] = useState("");
  const scrape = useNewsScrape((u: string) => newsApi.triggerScrape(u), {
    queuedMessage: "Analyzing article content and generating a summary…",
    failureMessage: "Couldn't analyze that article.",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    try {
      await scrape.run(url);
      setUrl("");
    } catch {
      // Shown via scrape.error; keep the URL so it can be fixed.
    }
  };

  return (
    <Card as="section" tone="filled" padding="md" className="mb-8" aria-labelledby="add-article-heading">
      <h2 id="add-article-heading" className="text-title-small font-semibold text-on-surface mb-3">
        Add article to radar
      </h2>
      <form onSubmit={handleSubmit} className="flex gap-2 items-start">
        <Field label="Article URL" labelVisible={false} className="flex-1">
          <Input
            size="sm"
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://techcrunch.com/article"
          />
        </Field>
        <Button type="submit" variant="filled" size="sm" loading={scrape.busy}>
          {scrape.busy ? "Analyzing…" : "Analyze"}
        </Button>
      </form>

      {scrape.progress && (
        <Alert icon={<Spinner />} className="mt-3">
          {scrape.progress}
        </Alert>
      )}
      {scrape.error && (
        <Alert
          variant="error"
          className="mt-3"
          action={
            <Button variant="text" size="sm" onClick={scrape.dismissError}>
              Dismiss
            </Button>
          }
        >
          {scrape.error}
        </Alert>
      )}
    </Card>
  );
}
