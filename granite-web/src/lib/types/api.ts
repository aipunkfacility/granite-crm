export type FunnelStage =
  | 'new'
  | 'email_sent'
  | 'email_opened'
  | 'tg_sent'
  | 'wa_sent'
  | 'replied'
  | 'interested'
  | 'not_interested'
  | 'unreachable';

export type Segment = 'A' | 'B' | 'C' | 'D' | 'spam';

export interface CompanyEmail {
  id: number;
  company_id: number;
  email: string;
  is_active: boolean;
  is_primary: boolean;
  sent_count: number;
  last_sent_at: string | null;
}

export interface Company {
  id: number;
  name: string;
  phones: string[];
  website: string | null;
  address: string | null;
  emails: string[];
  company_emails: CompanyEmail[];
  city: string;
  region: string;
  messengers: Record<string, string>;
  telegram: string | null;
  whatsapp: string | null;
  vk: string | null;
  segment: Segment | null;
  crm_score: number;
  cms: string | null;
  has_marquiz: boolean;
  is_network: boolean;
  tg_trust: Record<string, any>;
  funnel_stage: FunnelStage;
  email_sent_count: number;
  email_opened_count: number;
  tg_sent_count: number;
  wa_sent_count: number;
  last_contact_at: string | null;
  notes: string;
  stop_automation: boolean;
  merged_into: number | null;
  review_reason: string;
  needs_review: boolean;
  updated_at: string | null;
  sources: string[];
}

export interface ReEnrichData {
  name: string;
  phones: string[];
  emails: string[];
  website?: string | null;
  address?: string | null;
}

export interface ReEnrichPreviewResponse {
  company_id: number;
  before: ReEnrichData;
  after: ReEnrichData;
  has_changes: boolean;
}

export interface ReEnrichApplyRequest {
  name?: string;
  phones?: string[];
  emails?: string[];
  website?: string;
  address?: string;
  messengers?: Record<string, string>;
}

export interface FollowupItem {
  company_id: number;
  name: string;
  city: string;
  segment: string;
  crm_score: number;
  funnel_stage: FunnelStage;
  last_contact_at: string | null;
  next_followup_at: string | null;
  channel_suggested: 'email' | 'tg' | 'wa' | 'none';
  action_suggested: string;
  contact_data: string;
}

export interface Task {
  id: number;
  company_id: number;
  company_name?: string;
  company_city?: string;
  task_type: 'follow_up' | 'send_portfolio' | 'send_test_offer' | 'check_response' | 'other';
  description: string;
  due_date: string | null;
  status: 'pending' | 'done' | 'cancelled';
  priority: number;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Stats {
  total_companies: number;
  funnel: Record<string, number>;
  segments: Record<string, number>;
  with_telegram: number;
  with_whatsapp: number;
  with_email: number;
  top_cities: { city: string, count: number }[];
}

export interface Touch {
  id: number;
  company_id: number;
  channel: string;
  direction: string;
  subject: string | null;
  body: string | null;
  template_name: string | null;
  created_at: string | null;
}

// Network candidates
export interface NetworkCandidateCompany {
  id: number;
  name: string;
  city: string;
  website: string | null;
  phones: string[];
  emails: string[];
  is_network?: boolean;
}

export interface NetworkCandidateGroup {
  group_id: string;
  signal_type: 'email_domain' | 'website';
  signal_value: string;
  company_count: number;
  companies: NetworkCandidateCompany[];
  all_marked?: boolean;
}

export interface NetworkCandidatesResponse {
  groups: NetworkCandidateGroup[];
  total: number;
}

export interface ResolveNetworkGroupPayload {
  group_id: string;
  action: 'network' | 'duplicate';
  target_id?: number;
}

// Network list (redesign)
export interface TopCity {
  name: string;
  count: number;
}

export interface NetworkSummary {
  group_id: string;
  signal_type: string;
  signal_value: string;
  company_count: number;
  city_count: number;
  avg_score: number;
  email_count: number;
  phone_count: number;
  top_cities: TopCity[];
  network_type: 'franchise' | 'aggregator' | 'regional' | 'local';
  primary_email: string | null;
  segment_dist: Record<string, number>;
  contact_status: 'none' | 'sent';
  sent_count: number;
  total_count: number;
}

export interface NetworkListResponse {
  items: NetworkSummary[];
  total: number;
}

export interface NetworkDetailCompany {
  id: number;
  name: string;
  city: string;
  website: string | null;
  phones: string[];
  emails: string[];
  score: number;
}

export interface NetworkDetail extends NetworkSummary {
  companies: NetworkDetailCompany[];
}
