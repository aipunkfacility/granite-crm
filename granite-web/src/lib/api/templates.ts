import { apiClient } from './client';
import { PaginatedResponse } from '@/lib/types/api';

/** Тип содержимого шаблона */
export type BodyType = 'plain' | 'html';

/** Канал отправки */
export type Channel = 'email' | 'tg' | 'wa';

/** Шаблон сообщения — соответствует TemplateResponse в schemas.py */
export interface Template {
  name: string;
  channel: Channel;
  subject: string;
  body: string;
  body_type: BodyType;
  description: string;
}

/** Параметры для GET /templates */
export interface FetchTemplatesParams {
  channel?: Channel;
  page?: number;
  per_page?: number;
}

/** Ответ OkResponse от бэкенда */
export interface OkResponse {
  ok: boolean;
  message?: string;
}

/**
 * GET /templates — список шаблонов с пагинацией.
 * Бэкенд возвращает PaginatedResponse<Template>.
 */
export const fetchTemplates = async (
  params: FetchTemplatesParams = {},
): Promise<PaginatedResponse<Template>> => {
  const { data } = await apiClient.get<PaginatedResponse<Template>>('templates', { params });
  return data;
};

/**
 * GET /templates/{name} — один шаблон.
 */
export const fetchTemplate = async (name: string): Promise<Template> => {
  const { data } = await apiClient.get<Template>(`templates/${name}`);
  return data;
};

/**
 * POST /templates/reload — перезагрузить шаблоны из JSON без рестарта.
 * Использовать после ручного редактирования data/email_templates.json.
 */
export const reloadTemplates = async (): Promise<OkResponse> => {
  const { data } = await apiClient.post<OkResponse>('templates/reload');
  return data;
};
