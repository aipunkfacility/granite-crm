import { apiClient } from './client';
import { Stats } from '@/lib/types/api';

export const fetchStats = async (city?: string, region?: string): Promise<Stats> => {
  const params: Record<string, string> = {};
  if (city) params.city = city;
  if (region) params.region = region;
  const { data } = await apiClient.get<Stats>('stats', { params });
  return data;
};
