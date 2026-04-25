'use client';

import { useEffect } from "react";
import { useCompanies } from "@/lib/hooks/use-companies";
import { useCompanyFilters } from "@/lib/hooks/use-company-filters";
import { CompanyTable } from "@/components/companies/company-table";
import { CompaniesFilters } from "@/components/companies/CompaniesFilters";
import { CompanySheet } from "@/components/companies/CompanySheet";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { fetchCmsTypes } from "@/lib/api/companies";
import { apiClient } from "@/lib/api/client";

export function CompaniesPageContent() {
  const [page, setPage] = useState(1);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const {
    filters,
    setFilter,
    clearAll,
    activeCount,
    toApiParams,
  } = useCompanyFilters();

  const apiParams = toApiParams();
  const { data, isLoading, error } = useCompanies({
    ...apiParams,
    page,
    per_page: 50,
    order_by: 'crm_score',
    order_dir: 'desc',
  });

  // Сброс городов при смене региона
  useEffect(() => {
    setFilter('city', []);
  }, [filters.region, setFilter]);

  // Загрузка справочников для dropdown-фильтров
  const { data: cities } = useQuery({
    queryKey: ['cities', filters.region],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (filters.region) params.region = filters.region;
      const { data } = await apiClient.get<{ items: string[] }>('cities', { params });
      return data.items;
    },
    staleTime: 5 * 60 * 1000,
  });

  const { data: regions } = useQuery({
    queryKey: ['regions'],
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: string[] }>('regions');
      return data.items;
    },
    staleTime: 5 * 60 * 1000,
  });

  const { data: cmsTypes } = useQuery({
    queryKey: ['cms-types'],
    queryFn: fetchCmsTypes,
    staleTime: 5 * 60 * 1000,
  });

  // Сброс пагинации при изменении фильтров
  const prevFilterHash = useState(() => JSON.stringify(apiParams));
  const currentHash = JSON.stringify(apiParams);
  if (currentHash !== prevFilterHash[0]) {
    prevFilterHash[0] = currentHash;
    setTimeout(() => setPage(1), 0);
  }

  const handleSelectCompany = (companyId: number) => {
    setSelectedCompanyId(companyId);
    setSheetOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          {/* V-05: h1 font-semibold вместо font-bold */}
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Компании
            {activeCount > 0 && (
              <span className="ml-2 inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-sm font-medium text-primary">
                {activeCount} фильтр.
              </span>
            )}
          </h1>
          {/* V-27: подзаголовок text-sm */}
          <p className="text-sm text-muted-foreground">
            Управление базой потенциальных клиентов и стадиями воронки.
          </p>
        </div>

        <div className="relative w-full max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Поиск по названию..."
            className="pl-10"
            value={filters.search}
            onChange={(e) => setFilter('search', e.target.value)}
          />
        </div>
      </div>

      {/* Панель фильтров */}
      <CompaniesFilters
        filters={filters}
        onFilterChange={setFilter}
        onClearAll={clearAll}
        activeCount={activeCount}
        total={data?.total || 0}
        cities={cities || []}
        regions={regions || []}
        cmsTypes={cmsTypes || []}
      />

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-[400px] w-full" />
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-destructive">
          <h2 className="text-lg font-semibold">Ошибка загрузки данных</h2>
          <p>{(error as Error).message}</p>
        </div>
      ) : (
        <>
          <CompanyTable
            companies={data?.items || []}
            onSelectCompany={handleSelectCompany}
          />

          <div className="flex items-center justify-end text-sm text-muted-foreground py-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded border bg-card px-3 py-1 hover:bg-muted/50 disabled:opacity-50"
              >
                Назад
              </button>
              <span className="font-medium">Страница {page}</span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!data?.items || data.items.length < 50}
                className="rounded border bg-card px-3 py-1 hover:bg-muted/50 disabled:opacity-50"
              >
                Вперед
              </button>
            </div>
          </div>
        </>
      )}

      {/* V-01: Sheet вместо перехода на страницу */}
      <CompanySheet
        companyId={selectedCompanyId}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        onSelectCompany={handleSelectCompany}
      />
    </div>
  );
}
