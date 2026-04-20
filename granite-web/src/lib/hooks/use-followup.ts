import { useQuery } from '@tanstack/react-query';
import { fetchFollowup } from '@/lib/api/followup';

export function useFollowup(params: { page?: number; per_page?: number } = {}) {
  return useQuery({
    queryKey: ['followup', params],
    queryFn: () => fetchFollowup(params),
    refetchInterval: 60 * 1000, // Автообновление каждую минуту
  });
}
