import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { fetchCompanies, CompanyFilters } from '@/lib/api/companies';

export function useCompanies(filters: CompanyFilters) {
  return useQuery({
    queryKey: ['companies', filters],
    queryFn: () => fetchCompanies(filters),
    placeholderData: keepPreviousData,
    staleTime: 30 * 1000,
  });
}
