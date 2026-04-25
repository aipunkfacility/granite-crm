import { apiClient } from './client';

export interface AdminLoginResponse {
  token: string;
  expires_in: number;
}

export interface BatchResult {
  ok: boolean;
  processed: number;
}

/** Login — returns HMAC token with TTL */
export const adminLogin = async (password: string): Promise<AdminLoginResponse> => {
  const { data } = await apiClient.post<AdminLoginResponse>('admin/login', { password });
  return data;
};

/** Batch-approve: clear needs_review for given company IDs */
export const batchApprove = async (companyIds: number[], adminToken: string): Promise<BatchResult> => {
  const { data } = await apiClient.post<BatchResult>('companies/batch/approve', 
    { company_ids: companyIds },
    { headers: { 'X-Admin-Token': adminToken } }
  );
  return data;
};

/** Batch-spam: mark companies as spam with reason */
export const batchSpam = async (
  companyIds: number[],
  reason: string,
  adminToken: string,
): Promise<BatchResult> => {
  const { data } = await apiClient.post<BatchResult>('companies/batch/spam',
    { company_ids: companyIds, reason },
    { headers: { 'X-Admin-Token': adminToken } }
  );
  return data;
};
