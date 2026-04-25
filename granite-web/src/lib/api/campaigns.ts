import { apiClient } from './client';
import { PaginatedResponse } from '@/lib/types/api';

export interface Campaign {
  id: number;
  name: string;
  template_name: string;
  status: 'draft' | 'running' | 'paused' | 'completed';
  total_targets: number;
  sent_count: number;
  open_count: number;
  replied_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface Template {
  name: string;
  channel: 'email' | 'tg' | 'wa';
  subject?: string;
  body: string;
}

export const fetchCampaigns = async (params: { page?: number; per_page?: number } = {}): Promise<PaginatedResponse<Campaign>> => {
  const { data } = await apiClient.get<PaginatedResponse<Campaign>>('campaigns', { params });
  return data;
};

export const fetchTemplates = async (): Promise<Template[]> => {
  const { data } = await apiClient.get<Template[]>('templates');
  return data;
};

export const createCampaign = async (payload: { name: string; template_name: string; filters?: Record<string, any> }) => {
  const { data } = await apiClient.post('campaigns', payload);
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
