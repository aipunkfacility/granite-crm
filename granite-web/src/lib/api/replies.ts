import { apiClient } from './client';

export interface ReplyPreview {
  company_id: number;
  email_to: string;
  template_name: string;
  subject: string;
  body: string;
  body_type: 'plain' | 'html';
  stop_automation_warning?: string;  // FIX A6: предупреждение stop_automation из API
}

export interface SendReplyPayload {
  template_name: string;
  subject_override?: string;
}

export const previewReply = async (companyId: number, templateName: string): Promise<ReplyPreview> => {
  const { data } = await apiClient.post<ReplyPreview>(`companies/${companyId}/reply/preview`, {
    template_name: templateName,
  });
  return data;
};

export const sendReply = async (companyId: number, payload: SendReplyPayload): Promise<{ ok: boolean; id: number }> => {
  const { data } = await apiClient.post<{ ok: boolean; id: number }>(`companies/${companyId}/reply`, payload);
  return data;
};
