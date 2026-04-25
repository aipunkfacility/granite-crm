import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchTemplates,
  fetchTemplate,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  FetchTemplatesParams,
  CreateTemplatePayload,
  UpdateTemplatePayload,
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
 * Создать шаблон. После успеха — инвалидировать кэш списка.
 * Бэкенд может вернуть warnings о неизвестных плейсхолдерах.
 */
export function useCreateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTemplatePayload) => createTemplate(payload),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      if (result.warnings?.length) {
        toast.warning(`Неизвестные плейсхолдеры: ${result.warnings.join(', ')}`);
      }
      toast.success('Шаблон создан');
    },
    onError: (err: Error) => {
      toast.error(`Ошибка создания: ${err.message}`);
    },
  });
}

/**
 * Обновить шаблон. После успеха — инвалидировать кэш списка и конкретного шаблона.
 */
export function useUpdateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, payload }: { name: string; payload: UpdateTemplatePayload }) =>
      updateTemplate(name, payload),
    onSuccess: (result, { name }) => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      queryClient.invalidateQueries({ queryKey: ['templates', name] });
      if (result.warnings?.length) {
        toast.warning(`Неизвестные плейсхолдеры: ${result.warnings.join(', ')}`);
      }
      toast.success('Шаблон обновлён');
    },
    onError: (err: Error) => {
      toast.error(`Ошибка обновления: ${err.message}`);
    },
  });
}

/**
 * Удалить шаблон. Нельзя удалить, если используется в активной кампании (409).
 */
export function useDeleteTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteTemplate(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      toast.success('Шаблон удалён');
    },
    onError: (err: Error) => {
      toast.error(`Ошибка удаления: ${err.message}`);
    },
  });
}
