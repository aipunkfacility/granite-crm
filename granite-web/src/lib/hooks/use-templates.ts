import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchTemplates,
  fetchTemplate,
  reloadTemplates,
  FetchTemplatesParams,
} from '@/lib/api/templates';
import { toast } from 'sonner';

/**
 * Список шаблонов с опциональным фильтром по каналу и пагинацией.
 */
export function useTemplates(params: FetchTemplatesParams = {}) {
  return useQuery({
    queryKey: ['templates', params],
    queryFn: () => fetchTemplates(params),
    staleTime: 30 * 1000,
  });
}

/**
 * Один шаблон по имени.
 */
export function useTemplate(name: string | null) {
  return useQuery({
    queryKey: ['templates', name],
    queryFn: () => fetchTemplate(name!),
    enabled: !!name,
  });
}

/**
 * Перезагрузить шаблоны из JSON без рестарта сервера.
 * Использовать после ручного редактирования data/email_templates.json.
 */
export function useReloadTemplates() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => reloadTemplates(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      toast.success(result.message || 'Шаблоны перезагружены');
    },
    onError: (err: Error) => {
      toast.error(`Ошибка перезагрузки: ${err.message}`);
    },
  });
}
