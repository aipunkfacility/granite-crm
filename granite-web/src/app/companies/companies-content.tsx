'use client';

import { useEffect, useCallback } from "react";
import { useCompanies } from "@/lib/hooks/use-companies";
import { useCompanyFilters } from "@/lib/hooks/use-company-filters";
import { CompanyTable } from "@/components/companies/company-table";
import { CompaniesFilters } from "@/components/companies/CompaniesFilters";
import { CompanySheet } from "@/components/companies/CompanySheet";
import { BatchActionsBar } from "@/components/companies/BatchActionsBar";
import { BatchConfirmDialog, BatchAction } from "@/components/companies/BatchConfirmDialog";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { PresetManager } from "@/components/companies/PresetManager";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCmsTypes, fetchSourceTypes } from "@/lib/api/companies";
import { batchApprove, batchSpam } from "@/lib/api/admin";
import { apiClient } from "@/lib/api/client";
import { useAdmin } from "@/lib/admin-context";

export function CompaniesPageContent() {
  const [page, setPage] = useState(1);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sortKey, setSortKey] = useState('crm_score'); // frontend key
  const [orderDir, setOrderDir] = useState<'asc' | 'desc'>('desc');

  // Batch selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchDialogOpen, setBatchDialogOpen] = useState(false);
  const [batchAction, setBatchAction] = useState<BatchAction>('spam');

  const { isActive: isAdmin, token: adminToken } = useAdmin();
  const queryClient = useQueryClient();

  const {
    filters,
    setFilter,
    clearAll,
    applyPreset,
    activeCount,
    toApiParams,
  } = useCompanyFilters();

  const apiParams = toApiParams();
  const { data, isLoading, error } = useCompanies({
    ...apiParams,
    page,
    per_page: 50,
    order_by: sortKey === 'name' ? 'name_best' : sortKey,
    order_dir: orderDir,
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

  const { data: sourceTypes } = useQuery({
    queryKey: ['source-types'],
    queryFn: fetchSourceTypes,
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

  // --- Batch selection handlers ---
  const handleToggleSelect = useCallback((companyId: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(companyId)) next.delete(companyId);
      else next.add(companyId);
      return next;
    });
  }, []);

  const handleToggleSelectAll = useCallback(() => {
    const items = data?.items || [];
    if (!items.length) return;

    const allSelected = items.every(c => selectedIds.has(c.id));
    if (allSelected) {
      // Deselect all on current page
      setSelectedIds(prev => {
        const next = new Set(prev);
        items.forEach(c => next.delete(c.id));
        return next;
      });
    } else {
      // Select all on current page
      setSelectedIds(prev => {
        const next = new Set(prev);
        items.forEach(c => next.add(c.id));
        return next;
      });
    }
  }, [data?.items, selectedIds]);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleBatchSpam = useCallback(() => {
    setBatchAction('spam');
    setBatchDialogOpen(true);
  }, []);

  const handleBatchApprove = useCallback(() => {
    setBatchAction('approve');
    setBatchDialogOpen(true);
  }, []);

  const handleBatchConfirm = useCallback(async (action: BatchAction, reason?: string) => {
    if (!adminToken) throw new Error('Требуется авторизация администратора');
    const ids = Array.from(selectedIds);
    const total = ids.length;

    let processed: number;
    if (action === 'spam') {
      const res = await batchSpam(ids, reason || 'aggregator', adminToken);
      processed = res.processed;
    } else {
      const res = await batchApprove(ids, adminToken);
      processed = res.processed;
    }

    // Refresh data
    queryClient.invalidateQueries({ queryKey: ['companies'] });

    return { ok: processed > 0, processed, total };
  }, [adminToken, selectedIds, queryClient]);

  const handleBatchDialogClose = useCallback(() => {
    setBatchDialogOpen(false);
    setSelectedIds(new Set());
  }, []);

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

        <div className="flex items-center gap-3">
          <PresetManager filters={filters} onApplyPreset={applyPreset} />
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
        sourceTypes={sourceTypes || []}
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
            orderBy={sortKey}
            orderDir={orderDir}
            onSortChange={(key, dir) => { setSortKey(key); setOrderDir(dir); setPage(1); }}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onToggleSelectAll={handleToggleSelectAll}
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

      {/* Batch actions floating bar */}
      <BatchActionsBar
        selectedCount={selectedIds.size}
        onBatchSpam={handleBatchSpam}
        onBatchApprove={handleBatchApprove}
        onClearSelection={handleClearSelection}
        isAdmin={isAdmin}
      />

      {/* Batch confirmation dialog */}
      <BatchConfirmDialog
        isOpen={batchDialogOpen}
        action={batchAction}
        selectedCount={selectedIds.size}
        onClose={handleBatchDialogClose}
        onConfirm={handleBatchConfirm}
      />
    </div>
  );
}
