import { apiClient } from './client';
import { Company, PaginatedResponse, FunnelStage } from '@/lib/types/api';

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

export const fetchFollowup = async (params: { page?: number; per_page?: number } = {}): Promise<PaginatedResponse<FollowupItem>> => {
  const { data } = await apiClient.get<PaginatedResponse<FollowupItem>>('followup', { params });
  return data;
};

export const recordTouch = async (companyId: number, channel: string, note: string = "") => {
  const { data } = await apiClient.post(`companies/${companyId}/touches`, {
    channel,
    direction: 'outgoing',
    note
  });
  return data;
};
