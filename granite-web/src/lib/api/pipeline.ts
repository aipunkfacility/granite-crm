import { apiClient } from './client';

export interface PipelineStatusResponse {
  total_cities: number;
  returned: number;
  cities: PipelineCityStatus[];
}

export interface PipelineCityStatus {
  city: string;
  stage: 'scraped' | 'deduped' | 'enriched' | 'scored' | 'start';
  is_running: boolean;
  raw_count: number;
  company_count: number;
  enriched_count: number;
  enrichment_progress: number; // 0.0 - 1.0
  segments: Record<string, number>;
}

export interface CityReference {
  name: string;
  region: string;
  is_populated: boolean;
  is_doppelganger: boolean;
}

export const fetchPipelineStatus = async (): Promise<PipelineCityStatus[]> => {
  const { data } = await apiClient.get<PipelineStatusResponse>('pipeline/status');
  return data.cities; // Теперь возвращаем массив из объекта
};

export const fetchCities = async () => {
  const { data } = await apiClient.get<{ total: number, cities: CityReference[] }>('pipeline/cities');
  return data;
};

export const runPipeline = async (city: string, options: { force?: boolean, re_enrich?: boolean } = {}) => {
  const { data } = await apiClient.post('pipeline/run', { city, ...options });
  return data;
};
