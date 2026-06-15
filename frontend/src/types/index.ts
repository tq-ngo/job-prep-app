export interface User {
  id: string;
  email: string;
  leetcode_username?: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface AuthResponse extends Token {}

export interface JobApplication {
  id: string;
  company_name: string;
  job_title: string;
  job_url: string;
  location?: string;
  source: string;
  status: string;
  date_applied: string;
}

export interface SyncResponse {
  message: string;
  task_id: string;
}

export interface SyncStatus {
  task_id: string;
  status: string;
  result?: any;
}

export interface LeetCodeSnapshot {
  id: string;
  log_date: string;
  problems_solved: number;
  easy_solved: number;
  medium_solved: number;
  hard_solved: number;
}

export interface LeetCodeSubmission {
  id?: string;
  problem_name: string;
  submission_code: string;
  language: string;
  created_at?: string;
  next_review_due?: string;
  execution_performance?: string;
  conceptual_flaw?: string;
  time_complexity?: string;
  space_complexity?: string;
  user_id?: string;
}

export interface CorporateNewsItem {
  id: string;
  title: string;
  target_company: string;
  raw_content: string;
  url: string;
  ai_summary?: string;
  market_sentiment?: string;
  published_at: string;
  processed_at: string;
}
