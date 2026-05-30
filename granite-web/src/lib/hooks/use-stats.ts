import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '@/lib/api/stats';

export function useStats(city?: string, region?: string) {
  return useQuery({
    queryKey: ['stats', city, region],
    queryFn: () => fetchStats(city, region),
    staleTime: 60 * 1000,
    refetchInterval: 30 * 1000,
  });
}
