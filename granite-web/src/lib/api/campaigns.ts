import { apiClient } from './client';
import { PaginatedResponse } from '@/lib/types/api';

// Re-export Template from templates.ts для обратной совместимости
export { type Template, type Channel, type BodyType, fetchTemplates } from './templates';

// P4R-H7: Union type для статуса кампании — единый источник истины
export type CampaignStatus = 'draft' | 'running' | 'paused' | 'paused_daily_limit' | 'completed';

export interface Campaign {
  id: number;
  name: string;
  template_name: string;
  status: CampaignStatus;  // P4R-H7: был string, теперь union
  subject_a: string | null;
  subject_b: string | null;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  total_errors: number;
  total_recipients: number | null;
  created_at: string;
}

export interface CampaignDetail {
  id: number;
  name: string;
  template_name: string;
  status: CampaignStatus;  // P4R-H7: был string, теперь union как у Campaign
  filters: Record<string, any>;
  subject_a: string | null;
  subject_b: string | null;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  total_errors: number;
  open_rate: number;
  preview_recipients: number;
  validator_warnings: string[];
  started_at: string | null;
  completed_at: string | null;
}

export interface ABStats {
  variants: Record<string, {
    subject: string;
    sent: number;
    opened: number;
    replied: number;
    reply_rate: number;
  }>;
  winner: string | null;
  note: string | null;
}

export interface PreviewRecipientsResponse {
  total: number;
  sample: {
    id: number;
    name: string;
    city: string;
    emails: string[];
    segment: string | null;
    crm_score: number;
  }[];
  is_approximate?: boolean;  // P4R-M6: признак приблизительного подсчёта
}

export interface CreateCampaignPayload {
  name: string;
  template_name: string;
  filters?: Record<string, any>;
  subject_a?: string;
  subject_b?: string;
}

export const fetchCampaigns = async (params: { page?: number; per_page?: number } = {}): Promise<PaginatedResponse<Campaign>> => {
  const { data } = await apiClient.get<PaginatedResponse<Campaign>>('campaigns', { params });
  return data;
};

export const fetchCampaignDetail = async (campaignId: number): Promise<CampaignDetail> => {
  const { data } = await apiClient.get<CampaignDetail>(`campaigns/${campaignId}`);
  return data;
};

// P4R-M20: Типизируем возврат всех API-функций
export const createCampaign = async (payload: CreateCampaignPayload): Promise<{ ok: boolean; id?: number }> => {
  const { data } = await apiClient.post<{ ok: boolean; id?: number }>('campaigns', payload);
  return data;
};

export const updateCampaign = async (campaignId: number, payload: Partial<CreateCampaignPayload> & { filters?: Record<string, any> }): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.patch<{ ok: boolean }>(`campaigns/${campaignId}`, payload);
  return data;
};

export const runCampaign = async (campaignId: number): Promise<{ ok?: boolean; error?: string }> => {
  const { data } = await apiClient.post<{ ok?: boolean; error?: string }>(`campaigns/${campaignId}/run`);
  return data;
};

export const pauseCampaign = async (campaignId: number): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.patch<{ ok: boolean }>(`campaigns/${campaignId}`, { status: 'paused' });
  return data;
};

export const deleteCampaign = async (campaignId: number): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.delete<{ ok: boolean }>(`campaigns/${campaignId}`);
  return data;
};

export const fetchABStats = async (campaignId: number): Promise<ABStats> => {
  const { data } = await apiClient.get<ABStats>(`campaigns/${campaignId}/ab-stats`);
  return data;
};

export const previewRecipients = async (filters: Record<string, any>): Promise<PreviewRecipientsResponse> => {
  const { data } = await apiClient.post<PreviewRecipientsResponse>('campaigns/preview-recipients', filters);
  return data;
};

// P4R-H8: Удалена fetchCampaignProgress — мёртвый код с неправильным SSE-паттерном.
// Dashboard использует EventSource напрямую для SSE.
