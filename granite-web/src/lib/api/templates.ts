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
  created_at: string | null;
  updated_at: string | null;
}

/** Параметры для GET /templates */
export interface FetchTemplatesParams {
  channel?: Channel;
  page?: number;
  per_page?: number;
}

/** Данные для POST /templates (создание) */
export interface CreateTemplatePayload {
  name: string;
  channel: Channel;
  subject?: string;
  body: string;
  body_type?: BodyType;
  description?: string;
}

/** Данные для PUT /templates/{name} (обновление) */
export interface UpdateTemplatePayload {
  channel?: Channel;
  subject?: string;
  body?: string;
  body_type?: BodyType;
  description?: string;
}

/** Ответ OkResponse от бэкенда */
export interface OkResponse {
  ok: boolean;
  warnings?: string[];
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
 * POST /templates — создать шаблон.
 * Возвращает OkResponse (может содержать warnings о неизвестных плейсхолдерах).
 */
export const createTemplate = async (payload: CreateTemplatePayload): Promise<OkResponse> => {
  const { data } = await apiClient.post<OkResponse>('templates', payload);
  return data;
};

/**
 * PUT /templates/{name} — обновить шаблон.
 * Возвращает OkResponse (может содержать warnings).
 */
export const updateTemplate = async (
  name: string,
  payload: UpdateTemplatePayload,
): Promise<OkResponse> => {
  const { data } = await apiClient.put<OkResponse>(`templates/${name}`, payload);
  return data;
};

/**
 * DELETE /templates/{name} — удалить шаблон.
 * Нельзя удалить, если используется в активной кампании (409).
 */
export const deleteTemplate = async (name: string): Promise<OkResponse> => {
  const { data } = await apiClient.delete<OkResponse>(`templates/${name}`);
  return data;
};
