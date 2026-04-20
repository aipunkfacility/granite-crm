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

export interface Company {
  id: number;
  name: string;
  phones: string[];
  website: string | null;
  address: string | null;
  emails: string[];
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
  updated_at: string;
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
  by_segment: Record<string, number>;
  by_stage: Record<string, number>;
  with_telegram: number;
  with_email: number;
  top_cities: Record<string, number>;
}
