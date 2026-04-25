import { useQuery } from '@tanstack/react-query';
import { fetchCampaigns } from '@/lib/api/campaigns';
import { fetchTemplates } from '@/lib/api/templates';

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

/**
 * Лёгкий хук для загрузки шаблонов (используется на странице кампаний).
 * Для полноценной работы с шаблонами используйте useTemplates из use-templates.ts.
 */
export function useCampaignTemplates() {
  return useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const result = await fetchTemplates({ per_page: 500 });
      return result.items;
    },
  });
}
