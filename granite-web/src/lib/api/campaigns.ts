import { apiClient } from './client';
import { PaginatedResponse } from '@/lib/types/api';

// Re-export Template from templates.ts для обратной совместимости
export { type Template, type Channel, type BodyType, fetchTemplates } from './templates';

export interface Campaign {
  id: number;
  name: string;
  template_name: string;
  status: 'draft' | 'running' | 'paused' | 'paused_daily_limit' | 'completed';
  subject_a: string | null;
  subject_b: string | null;
  total_targets: number;
  sent_count: number;
  open_count: number;
  replied_count: number;
  total_errors: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface CampaignDetail {
  id: number;
  name: string;
  template_name: string;
  status: string;
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

export const createCampaign = async (payload: CreateCampaignPayload) => {
  const { data } = await apiClient.post('campaigns', payload);
  return data;
};

export const updateCampaign = async (campaignId: number, payload: Partial<CreateCampaignPayload> & { filters?: Record<string, any> }) => {
  const { data } = await apiClient.patch(`campaigns/${campaignId}`, payload);
  return data;
};

export const runCampaign = async (campaignId: number) => {
  const { data } = await apiClient.post(`campaigns/${campaignId}/run`);
  return data;
};

export const pauseCampaign = async (campaignId: number) => {
  const { data } = await apiClient.patch(`campaigns/${campaignId}`, { status: 'paused' });
  return data;
};

export const deleteCampaign = async (campaignId: number) => {
  const { data } = await apiClient.delete(`campaigns/${campaignId}`);
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

export const fetchCampaignProgress = async (campaignId: number): Promise<{
  status: string;
  sent: number;
  total: number;
  errors: number;
  started_at: string | null;
  completed_at: string | null;
}> => {
  // Используем SSE endpoint для получения текущего прогресса
  const response = await fetch(
    `${apiClient.defaults.baseURL}campaigns/${campaignId}/progress`
  );
  if (!response.ok) throw new Error('Failed to fetch progress');
  const reader = response.body?.getReader();
  if (!reader) throw new Error('No reader');
  const decoder = new TextDecoder();
  let result = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    result += decoder.decode(value, { stream: true });
  }
  // Parse SSE data
  const lines = result.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      return JSON.parse(line.slice(6));
    }
  }
  throw new Error('No SSE data received');
};
