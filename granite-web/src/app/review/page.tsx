'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchCompanies } from '@/lib/api/companies';
import { batchApprove, batchSpam } from '@/lib/api/admin';
import { Company } from '@/lib/types/api';
import { ReviewCard } from '@/components/companies/ReviewCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { useAdmin } from '@/lib/admin-context';
import { toast } from 'sonner';
import {
  CheckCircle2,
  ClipboardList,
  Loader2,
  Search,
  Shield,
  CheckSquare,
  Ban,
  X,
} from 'lucide-react';

export default function ReviewPage() {
  const queryClient = useQueryClient();
  const { isActive: isAdmin, token: adminToken } = useAdmin();
  const [search, setSearch] = useState('');
  const [focusIndex, setFocusIndex] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['review-queue', search],
    queryFn: () => fetchCompanies({
      needs_review: 1,
      include_spam: 0,
      per_page: 50,
      order_by: 'crm_score',
      order_dir: 'desc',
      search: search || undefined,
    }),
    staleTime: 10_000,
  });

  const companies = data?.items ?? [];
  const total = data?.total ?? 0;

  /* После resolve — обновить список */
  const handleResolved = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['review-queue'] });
    queryClient.invalidateQueries({ queryKey: ['companies'] });
    setSelectedIds(prev => {
      // Remove resolved companies from selection
      return prev;
    });
  }, [queryClient]);

  /* Selection helpers */
  const toggleSelect = useCallback((id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(companies.map(c => c.id)));
  }, [companies]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  /* Batch operations */
  const handleBatchApprove = async () => {
    if (!adminToken || selectedIds.size === 0) return;
    setBatchLoading(true);
    try {
      const result = await batchApprove(Array.from(selectedIds), adminToken);
      toast.success(`Подтверждено: ${result.processed} компаний`);
      clearSelection();
      handleResolved();
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleBatchSpam = async (reason: string = 'other') => {
    if (!adminToken || selectedIds.size === 0) return;
    setBatchLoading(true);
    try {
      const result = await batchSpam(Array.from(selectedIds), reason, adminToken);
      toast.success(`В спам: ${result.processed} компаний`);
      clearSelection();
      handleResolved();
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    } finally {
      setBatchLoading(false);
    }
  };

  /* Keyboard shortcuts: A=approve, S=spam, D=duplicate, ↓=next, ↑=prev */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      /* Не перехватываем, если фокус в input/textarea */
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault();
        setFocusIndex(i => Math.min(i + 1, companies.length - 1));
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault();
        setFocusIndex(i => Math.max(i - 1, 0));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [companies.length]);

  /* Сброс фокуса при изменении списка */
  useEffect(() => {
    if (focusIndex >= companies.length) {
      setFocusIndex(Math.max(0, companies.length - 1));
    }
  }, [companies.length, focusIndex]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground flex items-center gap-3">
            <ClipboardList className="h-8 w-8 text-primary" />
            На проверке
            {total > 0 && (
              <Badge variant="default" className="text-sm px-2.5 py-0.5">
                {total}
              </Badge>
            )}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Компании, требующие ручной проверки. Используйте клавиши для быстрой работы.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Поиск в очереди..."
              className="pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Keyboard hint + admin hint */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">A</kbd> Подтвердить
        </span>
        <span className="inline-flex items-center gap-1">
          <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">S</kbd> В спам
        </span>
        <span className="inline-flex items-center gap-1">
          <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">D</kbd> Дубль
        </span>
        <span className="inline-flex items-center gap-1">
          <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">↑↓</kbd> Навигация
        </span>
        {isAdmin && (
          <span className="inline-flex items-center gap-1 text-success">
            <Shield className="h-3 w-3" /> Batch-режим активен
          </span>
        )}
      </div>

      {/* Batch toolbar (admin only, when selection active) */}
      {isAdmin && selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
          <span className="text-sm font-medium text-foreground">
            Выбрано: {selectedIds.size}
          </span>
          <div className="flex-1" />
          <Button
            variant="outline"
            size="sm"
            className="border-success/30 text-success hover:bg-success/10"
            onClick={handleBatchApprove}
            disabled={batchLoading}
          >
            {batchLoading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <CheckSquare className="mr-1.5 h-3.5 w-3.5" />}
            Подтвердить все
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-destructive/30 text-destructive hover:bg-destructive/10"
            onClick={() => handleBatchSpam('other')}
            disabled={batchLoading}
          >
            {batchLoading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Ban className="mr-1.5 h-3.5 w-3.5" />}
            В спам все
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearSelection}
          >
            <X className="mr-1.5 h-3.5 w-3.5" />
            Сбросить
          </Button>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <Loader2 className="h-10 w-10 text-primary animate-spin" />
          <p className="text-muted-foreground animate-pulse">Загрузка очереди...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-destructive">
          <h2 className="text-lg font-semibold">Ошибка загрузки</h2>
          <p>{(error as Error).message}</p>
        </div>
      ) : companies.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
            <CheckCircle2 className="h-8 w-8 text-success" />
          </div>
          <h2 className="text-xl font-semibold text-foreground">Всё проверено!</h2>
          <p className="text-muted-foreground text-center max-w-sm">
            Нет компаний, требующих проверки. Когда появятся новые — они будут здесь.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Progress bar + select all (admin) */}
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            {isAdmin && (
              <Checkbox
                checked={selectedIds.size === companies.length && companies.length > 0}
                onCheckedChange={(checked) => {
                  if (checked) selectAll();
                  else clearSelection();
                }}
              />
            )}
            <span>Показано {companies.length} из {total}</span>
            <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-success rounded-full transition-all"
                style={{ width: '100%' }}
              />
            </div>
            {isAdmin && selectedIds.size > 0 && (
              <Button variant="link" size="sm" className="text-xs h-auto p-0" onClick={selectAll}>
                Выбрать все
              </Button>
            )}
          </div>

          {/* Review cards */}
          <div className="space-y-3">
            {companies.map((company, idx) => (
              <div key={company.id} className="relative flex items-start gap-2">
                {isAdmin && (
                  <div className="pt-5 pl-1">
                    <Checkbox
                      checked={selectedIds.has(company.id)}
                      onCheckedChange={() => toggleSelect(company.id)}
                    />
                  </div>
                )}
                <div className="flex-1 relative">
                  {idx === focusIndex && (
                    <div className="absolute -left-1 top-0 bottom-0 w-1 rounded-full bg-primary" />
                  )}
                  <ReviewCard
                    company={company}
                    onResolved={handleResolved}
                    focused={idx === focusIndex}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
