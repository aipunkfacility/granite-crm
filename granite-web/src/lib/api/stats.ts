import { apiClient } from './client';
import { Stats } from '@/lib/types/api';

export const fetchStats = async (city?: string): Promise<Stats> => {
  const params = city ? { city } : {};
  const { data } = await apiClient.get<Stats>('stats', { params });
  return data;
};
