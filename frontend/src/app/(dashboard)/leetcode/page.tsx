"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getReviewQueue, submitLeetCode } from "@/api/leetcode";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Brain, Code2, History, Loader2, Sparkles } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";

const submissionSchema = z.object({
  problem_name: z.string().min(1, "Problem name is required"),
  submission_code: z.string().min(1, "Code is required"),
  language: z.string().min(1, "Language is required"),
});

type SubmissionFormValues = z.infer<typeof submissionSchema>;

export default function LeetCodePage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: reviewQueue, isLoading: isQueueLoading } = useQuery({
    queryKey: ["leetcode-review"],
    queryFn: getReviewQueue,
  });

  const { register, handleSubmit, reset, formState: { errors } } = useForm<SubmissionFormValues>({
    resolver: zodResolver(submissionSchema),
    defaultValues: { language: "python" },
  });

  const submissionMutation = useMutation({
    mutationFn: (data: SubmissionFormValues) => submitLeetCode({ ...data, user_id: user?.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leetcode-review"] });
      setIsDialogOpen(false);
      reset();
    },
  });

  const onSubmit = (data: SubmissionFormValues) => {
    submissionMutation.mutate(data);
  };

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">LeetCode Tracker</h2>
          <p className="text-muted-foreground">
            Track your progress and review problems using spaced repetition.
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger render={<Button><Code2 className="mr-2 h-4 w-4" />New Submission</Button>} />
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Add LeetCode Submission</DialogTitle>
              <DialogDescription>
                Paste your solved code here. AI will analyze it and schedule a review.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-4">
              <div className="space-y-2">
                <Input placeholder="Problem Title (e.g., Two Sum)" {...register("problem_name")} />
                {errors.problem_name && <p className="text-xs text-red-500">{errors.problem_name.message}</p>}
              </div>
              <div className="space-y-2">
                <Textarea 
                  placeholder="Paste your code here..." 
                  className="min-h-[200px] font-mono text-sm"
                  {...register("submission_code")} 
                />
                {errors.submission_code && <p className="text-xs text-red-500">{errors.submission_code.message}</p>}
              </div>
              <Button type="submit" className="w-full" disabled={submissionMutation.isPending}>
                {submissionMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    AI is analyzing...
                  </>
                ) : "Submit for AI Analysis"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
        <div className="md:col-span-2 space-y-4">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-primary" />
            <h3 className="text-xl font-semibold">Review Queue</h3>
          </div>
          {isQueueLoading ? (
            <p>Loading queue...</p>
          ) : reviewQueue?.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-10 text-muted-foreground">
                <Sparkles className="h-10 w-10 mb-2 opacity-20" />
                <p>No problems due for review today. Good job!</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {reviewQueue?.map((item) => (
                <Card key={item.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{item.problem_name}</CardTitle>
                      <Badge variant="outline">Due: {new Date(item.next_review_due!).toLocaleDateString()}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <span className="font-semibold">Time:</span> {item.time_complexity}
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="font-semibold">Space:</span> {item.space_complexity}
                      </div>
                    </div>
                    {item.conceptual_flaw && (
                      <div className="bg-orange-500/5 p-3 rounded-md border border-orange-500/10">
                        <p className="text-xs font-bold text-orange-600 uppercase mb-1 flex items-center gap-1">
                          <Brain className="h-3 w-3" /> AI Insight: Conceptual Flaw
                        </p>
                        <p className="text-sm">{item.conceptual_flaw}</p>
                      </div>
                    )}
                  </CardContent>
                  <CardFooter>
                    <Button variant="outline" size="sm" className="w-full">
                      Start Review
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <h3 className="text-xl font-semibold">Learning Progress</h3>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Spaced Repetition Stats</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span>Total Problems Solved</span>
                  <span className="font-bold">0</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>Problems for Review</span>
                  <span className="font-bold">{reviewQueue?.length || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
