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

export const fetchCmsTypes = async (): Promise<string[]> => {
  const { data } = await apiClient.get<{ items: string[] }>('cms-types');
  return data.items;
};
