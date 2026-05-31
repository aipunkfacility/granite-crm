import { apiClient } from './client';
import { NetworkCandidatesResponse, ResolveNetworkGroupPayload } from '@/lib/types/api';

export const fetchNetworkCandidates = async (): Promise<NetworkCandidatesResponse> => {
  const { data } = await apiClient.get<NetworkCandidatesResponse>('network-candidates');
  return data;
};

export const resolveNetworkGroup = async (payload: ResolveNetworkGroupPayload): Promise<{ ok: boolean; message: string }> => {
  const { data } = await apiClient.post<{ ok: boolean; message: string }>('network-candidates/resolve', payload);
  return data;
};
