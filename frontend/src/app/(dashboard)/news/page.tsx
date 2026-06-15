"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getNews, ingestNews } from "@/api/news";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, Newspaper, Plus, Loader2, Search } from "lucide-react";
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useState } from "react";

const newsSchema = z.object({
  title: z.string().min(1),
  target_company: z.string().min(1),
  url: z.string().url(),
  raw_content: z.string().min(1),
  published_at: z.string().min(1),
});

type NewsFormValues = z.infer<typeof newsSchema>;

export default function NewsPage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: news, isLoading } = useQuery({
    queryKey: ["news"],
    queryFn: getNews,
  });

  const { register, handleSubmit, reset } = useForm<NewsFormValues>({
    resolver: zodResolver(newsSchema),
    defaultValues: {
      published_at: new Date().toISOString(),
    },
  });

  const ingestMutation = useMutation({
    mutationFn: ingestNews,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["news"] });
      setIsDialogOpen(false);
      reset();
    },
  });

  const onSubmit = (data: NewsFormValues) => {
    ingestMutation.mutate(data);
  };

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Tech News Synthesizer</h2>
          <p className="text-muted-foreground">
            Stay updated with the latest tech news, hiring trends, and market shifts.
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger render={<Button><Plus className="mr-2 h-4 w-4" />Ingest Article</Button>} />
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Ingest Tech News</DialogTitle>
              <DialogDescription>
                Add an article for AI synthesis and sentiment analysis.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-4">
              <Input placeholder="Article Title" {...register("title")} />
              <Input placeholder="Target Company (e.g. Google)" {...register("target_company")} />
              <Input placeholder="URL" {...register("url")} />
              <Textarea placeholder="Raw Content (for analysis)" {...register("raw_content")} />
              <Button type="submit" className="w-full" disabled={ingestMutation.isPending}>
                {ingestMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Ingest & Synthesize"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {isLoading ? (
          <p>Loading news...</p>
        ) : news?.length === 0 ? (
          <div className="col-span-2 flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Newspaper className="h-12 w-12 mb-4 opacity-20" />
            <p>No news items found. Try ingesting a new article.</p>
          </div>
        ) : (
          news?.map((item) => (
            <Card key={item.id} className="overflow-hidden">
              <CardHeader className="bg-muted/30 pb-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <Badge variant="outline" className="mb-2">
                      {item.target_company}
                    </Badge>
                    <CardTitle className="text-xl leading-tight">{item.title}</CardTitle>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => window.open(item.url, "_blank")}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="pt-6 space-y-4">
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-primary uppercase tracking-wider">AI Summary</p>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.ai_summary || "Synthesis in progress..."}
                  </p>
                </div>
                {item.market_sentiment && (
                  <div className="inline-flex items-center rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-600 ring-1 ring-inset ring-emerald-500/20">
                    {item.market_sentiment}
                  </div>
                )}
              </CardContent>
              <CardFooter className="bg-muted/10 text-xs text-muted-foreground border-t">
                Published: {new Date(item.published_at).toLocaleDateString()}
              </CardFooter>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
