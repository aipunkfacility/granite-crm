import { apiClient } from './client';
import { Company, PaginatedResponse } from '@/lib/types/api';

export interface CompanyFilters {
  // Существующие (фиксим типы)
  city?: string[];
  region?: string;                  // ДОБАВЛЕНО
  segment?: string[];               // ИЗМЕНЕНО: str → str[] (multi-select)
  funnel_stage?: string;
  has_telegram?: 0 | 1 | undefined;  // ИЗМЕНЕНО: boolean → 0|1
  has_whatsapp?: 0 | 1 | undefined;  // ИЗМЕНЕНО: boolean → 0|1
  has_email?: 0 | 1 | undefined;     // ИЗМЕНЕНО: boolean → 0|1
  min_score?: number;
  max_score?: number;                 // НОВОЕ
  search?: string;
  page?: number;
  per_page?: number;
  order_by?: string;
  order_dir?: 'asc' | 'desc';

  // Новые фильтры
  is_network?: 0 | 1 | undefined;
  has_website?: 0 | 1 | undefined;
  has_vk?: 0 | 1 | undefined;
  has_address?: 0 | 1 | undefined;
  needs_review?: 0 | 1 | undefined;
  stop_automation?: 0 | 1 | undefined;
  cms?: string;
  has_marquiz?: 0 | 1 | undefined;

  // Фаза 1: Спам/удалённые
  include_spam?: 0 | 1 | 2;  // 0=hide, 1=show, 2=only spam
  include_deleted?: 0 | 1;   // 0=hide, 1=show

  // Фаза 2: TG Trust
  tg_trust_min?: number;     // 0-3
  tg_trust_max?: number;     // 0-3

  // Фаза 10: Source
  source?: string;           // jsprav, web_search, 2gis, etc.
}

export const fetchCompanies = async (params: CompanyFilters): Promise<PaginatedResponse<Company>> => {
  const queryParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;

    if (Array.isArray(value)) {
      value.forEach(v => queryParams.append(key, String(v)));
    } else {
      queryParams.append(key, String(value));
    }
  });

  const { data } = await apiClient.get<PaginatedResponse<Company>>('companies', {
    params: queryParams,
  });
  return data;
};

export const fetchCompany = async (id: number): Promise<Company> => {
  const { data } = await apiClient.get<Company>(`companies/${id}`);
  return data;
};

export const updateCompany = async (id: number, updates: Partial<Company>): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.patch<{ ok: boolean }>(`companies/${id}`, updates);
  return data;
};

export const reEnrichPreview = async (id: number): Promise<any> => {
  const { data } = await apiClient.post(`companies/${id}/re-enrich-preview`);
  return data;
};

export const reEnrichApply = async (id: number, updates: any): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.post(`companies/${id}/re-enrich-apply`, updates);
  return data;
};

// Mark-spam / unmark-spam
export const markSpam = async (id: number, reason: string, note?: string): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.post(`companies/${id}/mark-spam`, { reason, note });
  return data;
};

export const unmarkSpam = async (id: number): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.post(`companies/${id}/unmark-spam`);
  return data;
};

// Mark-duplicate
export const markDuplicate = async (id: number, targetId: number): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.post(`companies/${id}/mark-duplicate`, { target_id: targetId });
  return data;
};

// Resolve-review
export interface ResolveReviewPayload {
  action: 'approve' | 'spam' | 'duplicate';
  reason?: string;
  target_id?: number;
}

export const resolveReview = async (id: number, payload: ResolveReviewPayload): Promise<{ ok: boolean }> => {
  const { data } = await apiClient.post(`companies/${id}/resolve-review`, payload);
  return data;
};

export const fetchCmsTypes = async (): Promise<string[]> => {
  const { data } = await apiClient.get<{ items: string[] }>('cms-types');
  return data.items;
};

export const fetchSourceTypes = async (): Promise<string[]> => {
  const { data } = await apiClient.get<{ items: string[] }>('source-types');
  return data.items;
};
