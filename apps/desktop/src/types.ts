export type Locale = "zh-CN" | "en-US";
export type CapabilityStatus = "available" | "estimated" | "partial" | "unavailable" | "invalid";

export interface Settings {
  product_name: string;
  player_identifier: string | null;
  locale: Locale;
  onboarding_complete: boolean;
  scan_directories: string[];
  data_dir: string;
  provider: ProviderSettings | null;
}

export interface ProviderSettings {
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
  output_mode: "structured_output" | "json_mode" | "plain_json_prompt";
}

export interface DemoItem {
  demo_id: string;
  filename: string;
  size_bytes: number;
  sha256: string;
  imported_at: string;
  exists: boolean;
  status: string;
  source_type: string;
}

export interface MatchItem {
  match_id: string;
  demo_id: string;
  filename: string | null;
  map_name: string;
  played_at: string;
  rounds: number;
  kills: number | null;
  deaths: number | null;
  kd: number | null;
  adr: number | null;
  round_wins: number | null;
  quality: Record<string, CapabilityStatus>;
  parse_status: string;
  source_exists: boolean;
  parser_version: string;
  schema_version: string;
  player_match_status: "matched" | "unavailable";
}

export interface JobItem {
  job_id: string;
  type: string;
  status: string;
  stage: string;
  progress: number;
  created_at: string;
  error_code: string | null;
  error_message: string | null;
}

export interface ReportListItem {
  analysis_id: string;
  status: string;
  report_kind: "local" | "ai";
  source_changed: boolean;
  created_at: string;
  match_count: number;
  report_available: boolean;
  one_sentence_summary: string | null;
  rounds_analyzed: number | null;
  data_confidence: number | null;
}

export interface PriorityIssue {
  issue_id: string;
  title: string;
  category: string;
  severity: string;
  priority_rank: number;
  impact_score: number;
  evidence_summary: string;
  why_it_matters: string;
  trend: string;
  confidence: number;
  metric_refs: string[];
  review_round_ids: string[];
  next_match_rule: string;
}

export interface ReviewRound {
  round_id: string;
  review_type: string;
  title: string;
  why_review: string;
  issue_tags: string[];
  key_event_summary: string;
  review_questions: string[];
  recommended_action: string;
}

export interface Strength {
  strength_id: string;
  title: string;
  category: string;
  evidence_summary: string;
  trend: string;
  confidence: number;
  maintain_rule: string;
}

export interface CoachingReport {
  schema_version: string;
  report_summary: {
    overall_status: string;
    one_sentence_summary: string;
    matches_analyzed: number;
    rounds_analyzed: number;
    data_confidence: number;
    analysis_scope: string;
  };
  priority_issues: PriorityIssue[];
  review_rounds: ReviewRound[];
  strengths: Strength[];
  dimension_summaries: Record<string, {
    grade: string;
    status: string;
    main_positive: string | null;
    main_negative: string | null;
    metric_refs: string[];
  }>;
  training_plan: {
    period: string;
    primary_goals: Array<{
      title: string;
      metric_id: string;
      current_value: number | null;
      target_value: number | null;
      behavior_rule: string;
    }>;
    maintenance_goals: Array<{
      title: string;
      metric_id: string;
      current_value: number | null;
      target_value: number | null;
      behavior_rule: string;
    }>;
  };
  warnings: string[];
}
