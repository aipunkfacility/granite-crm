import { useQuery } from '@tanstack/react-query';
import { fetchCampaigns, fetchTemplates } from '@/lib/api/campaigns';

export function useCampaigns(params: { page?: number; per_page?: number } = {}) {
  return useQuery({
    queryKey: ['campaigns', params],
    queryFn: () => fetchCampaigns(params),
    refetchInterval: (data) => {
      // Если есть запущенные кампании, обновляем чаще (каждые 5 сек)
      const hasRunning = data?.state.data?.items.some(c => c.status === 'running');
      return hasRunning ? 5000 : 30000;
    }
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchTemplates(),
  });
}
