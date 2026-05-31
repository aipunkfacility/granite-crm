import { apiClient } from './client';
import { NetworkCandidatesResponse, ResolveNetworkGroupPayload } from '@/lib/types/api';

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
