export interface Lead {
  id: string;
  name: string;
  email: string;
  phone: string;
  company: string;
  website: string;
  source: string;
  service: string;
  enquiry: string;
  budget: string;
  deadline: string;
  contact_method: string;
  status: string;
  score: number;
  category: string;
  urgency: string;
  consent: boolean;
  opted_out: boolean;
  replied: boolean;
  paused: boolean;
  owner: string;
  created_at: string;
  correlation_id: string;
  missing: string[];
  review_reasons: string[];
  requirements: {
    summary?: string;
    deliverables?: string[];
    suggestions?: string[];
  };
  scoring: { rule: string; weight: number; points: number; reason: string }[];
  probable_duplicate: string | null;
}
export interface Message {
  id: string;
  lead_id: string;
  kind: string;
  content: string;
  subject: string;
  approval: string;
  state: string;
  error: string | null;
  provider: string;
  prompt_version: string;
  revisions: { content: string; subject: string; at: string }[];
  lead?: Lead;
}
export interface Detail {
  lead: Lead;
  events: {
    id: string;
    kind: string;
    actor: string;
    created_at: string;
    detail: Record<string, unknown>;
  }[];
  messages: Message[];
  followups: {
    id: string;
    position: number;
    scheduled_at: string;
    state: string;
    stop_reason: string | null;
  }[];
  crm: { state: string; attempts: number; error: string | null } | null;
}
export interface Run {
  id: string;
  lead_id: string;
  workflow: string;
  correlation_id: string;
  status: string;
  attempts: number;
  error: string | null;
  retry_state: string;
  started_at: string;
  completed_at: string | null;
}
export interface Overview {
  total: number;
  new: number;
  qualified: number;
  review: number;
  bookings: number;
  conversion: number;
  failed_runs: number;
  average_processing_seconds: number;
  estimated_ai_cost: number | null;
  approval_pending: number;
}
export interface Rules {
  budget_weight: number;
  service_weight: number;
  completeness_weight: number;
  timeline_weight: number;
  business_weight: number;
  geography_weight: number;
  spam_penalty: number;
  low_budget_cap: number;
  high_threshold: number;
  medium_threshold: number;
  supported_services: string[];
  allowed_countries: string[];
  probable_duplicates: boolean;
  review_urgent: boolean;
  booking_url: string;
  followup_days: number[];
  safe_automation: boolean;
  notifications_enabled: boolean;
}
export interface Settings {
  rules: Rules;
  providers: {
    llm: string;
    crm: string;
    email: string;
    slack_configured: boolean;
    orchestration: string;
  };
  demo_defaults: boolean;
}
