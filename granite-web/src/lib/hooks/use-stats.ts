import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '@/lib/api/stats';

export function useStats(city?: string) {
  return useQuery({
    queryKey: ['stats', city],
    queryFn: () => fetchStats(city),
    staleTime: 60 * 1000, // Статистику можно обновлять раз в минуту
  });
}
