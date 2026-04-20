import { useQuery } from '@tanstack/react-query';
import { fetchPipelineStatus, fetchCities } from '@/lib/api/pipeline';

export function usePipelineStatus() {
  return useQuery({
    queryKey: ['pipeline', 'status'],
    queryFn: () => fetchPipelineStatus(),
    refetchInterval: 10000, // Обновляем каждые 10 секунд
  });
}

export function useCities() {
  return useQuery({
    queryKey: ['pipeline', 'cities'],
    queryFn: () => fetchCities(),
  });
}
