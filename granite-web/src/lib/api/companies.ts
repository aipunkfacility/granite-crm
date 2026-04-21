import { apiClient } from './client';
import { Company, PaginatedResponse } from '@/lib/types/api';

export interface CompanyFilters {
  city?: string[];
  segment?: string;
  funnel_stage?: string;
  has_telegram?: boolean;
  has_whatsapp?: boolean;
  has_email?: boolean;
  min_score?: number;
  search?: string;
  page?: number;
  per_page?: number;
  order_by?: string;
  order_dir?: 'asc' | 'desc';
}

export const fetchCompanies = async (params: CompanyFilters): Promise<PaginatedResponse<Company>> => {
  const queryParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    
    if (Array.isArray(value)) {
      value.forEach(v => queryParams.append(key, v));
    } else {
      queryParams.append(key, String(value));
    }
  });

  // Убрали ведущий слэш: '/companies' -> 'companies'
  const { data } = await apiClient.get<PaginatedResponse<Company>>('companies', {
    params: queryParams,
  });
  return data;
};

export const fetchCompany = async (id: number): Promise<Company> => {
  // Убрали ведущий слэш
  const { data } = await apiClient.get<Company>(`companies/${id}`);
  return data;
};

export const updateCompany = async (id: number, updates: Partial<Company>): Promise<{ ok: boolean }> => {
  // Убрали ведущий слэш
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
