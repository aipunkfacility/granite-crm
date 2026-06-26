import { apiClient } from './client';
import {
  NetworkCandidatesResponse, ResolveNetworkGroupPayload,
  NetworkListResponse, NetworkDetail, NetworkEmail,
} from '@/lib/types/api';

export interface NetworkCandidatesParams {
  signal_type?: string;
  min_companies?: number;
  include_resolved?: boolean;
}

export const fetchNetworkCandidates = async (
  params?: NetworkCandidatesParams,
): Promise<NetworkCandidatesResponse> => {
  const { data } = await apiClient.get<NetworkCandidatesResponse>('network-candidates', { params });
  return data;
};

export const resolveNetworkGroup = async (payload: ResolveNetworkGroupPayload): Promise<{ ok: boolean; message: string }> => {
  const { data } = await apiClient.post<{ ok: boolean; message: string }>('network-candidates/resolve', payload);
  return data;
};

export interface NetworksParams {
  signal_type?: string;
  min_companies?: number;
  network_type?: string;
  contact_status?: string;
}

export const fetchNetworks = async (
  params?: NetworksParams,
): Promise<NetworkListResponse> => {
  const { data } = await apiClient.get<NetworkListResponse>('networks', { params });
  return data;
};

export const fetchNetworkDetail = async (
  groupId: string,
): Promise<NetworkDetail> => {
  const { data } = await apiClient.get<NetworkDetail>(`networks/${encodeURIComponent(groupId)}`);
  return data;
};

export const unmarkNetwork = async (
  groupId: string,
): Promise<{ ok: boolean; message: string }> => {
  const { data } = await apiClient.post<{ ok: boolean; message: string }>(
    `networks/${encodeURIComponent(groupId)}/unmark`,
  );
  return data;
};

export const spamNetwork = async (
  groupId: string,
  reason: string,
  adminToken: string,
  note?: string,
): Promise<{ ok: boolean; processed: number }> => {
  const { data } = await apiClient.post<{ ok: boolean; processed: number }>(
    `networks/${encodeURIComponent(groupId)}/spam`,
    { reason, note: note ?? '' },
    { headers: { 'X-Admin-Token': adminToken } },
  );
  return data;
};

export interface ToggleEmailPayload {
  email: string;
  is_disabled: boolean;
  reason?: string;
}

export const listNetworkEmails = async (
  networkId: number,
): Promise<NetworkEmail[]> => {
  const { data } = await apiClient.get<NetworkEmail[]>(
    `networks/${networkId}/emails`,
  );
  return data;
};

export const toggleNetworkEmail = async (
  networkId: number,
  payload: ToggleEmailPayload,
): Promise<{ ok: boolean; message: string }> => {
  const { data } = await apiClient.post<{ ok: boolean; message: string }>(
    `networks/${networkId}/emails/toggle`,
    payload,
  );
  return data;
};
