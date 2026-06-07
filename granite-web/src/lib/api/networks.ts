import { apiClient } from './client';
import {
  NetworkCandidatesResponse, ResolveNetworkGroupPayload,
  NetworkListResponse, NetworkDetail,
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
