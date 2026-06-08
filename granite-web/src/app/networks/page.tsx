'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchNetworks, NetworksParams } from '@/lib/api/networks';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Loader2, AlertCircle, RefreshCw, Network,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { NetworkCard } from '@/components/networks/NetworkCard';

export default function NetworksPage() {
  const router = useRouter();
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [signalFilter, setSignalFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [minCompanies, setMinCompanies] = useState(2);
  const params: NetworksParams = {};
  if (typeFilter) params.network_type = typeFilter;
  if (signalFilter) params.signal_type = signalFilter;
  if (statusFilter) params.contact_status = statusFilter;
  if (minCompanies > 2) params.min_companies = minCompanies;

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['networks', params],
    queryFn: () => fetchNetworks(params),
    staleTime: 10_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasActiveFilter = typeFilter || signalFilter || statusFilter || minCompanies > 2;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <Network className="h-8 w-8 text-primary" />
            Сети
            {total > 0 && <Badge variant="default" className="text-sm">{total}</Badge>}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Компании, объединённые общим сайтом, телефоном или email-доменом.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => router.push('/networks/candidates')}>
          Кандидаты на разметку
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 p-4 rounded-lg border bg-muted/30">
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          aria-label="Фильтр по типу сети"
        >
          <option value="">Все типы</option>
          <option value="franchise">Франчайзинг</option>
          <option value="aggregator">Агрегатор</option>
          <option value="regional">Региональная</option>
          <option value="local">Локальная</option>
        </select>
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={signalFilter}
          onChange={(e) => setSignalFilter(e.target.value)}
          aria-label="Фильтр по типу связи"
        >
          <option value="">Любой сигнал</option>
          <option value="website">Сайт</option>
          <option value="phone">Телефон</option>
          <option value="email_domain">Email-домен</option>
        </select>
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Фильтр по статусу контакта"
        >
          <option value="">Статус любой</option>
          <option value="none">Не отправлено</option>
          <option value="sent">Отправлено</option>
        </select>
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Мин. филиалов:</label>
          <select
            className="h-9 rounded-md border bg-background px-3 text-sm"
            value={minCompanies}
            onChange={(e) => setMinCompanies(Number(e.target.value))}
          >
            <option value={2}>2+</option>
            <option value={5}>5+</option>
            <option value={10}>10+</option>
            <option value={20}>20+</option>
          </select>
        </div>
        {isFetching && !isLoading && (
          <Loader2 className="h-4 w-4 text-primary animate-spin ml-auto" />
        )}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border bg-card animate-pulse overflow-hidden">
              <div className="p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-36 rounded bg-muted" />
                  <div className="h-5 w-14 rounded-full bg-muted" />
                  <div className="h-5 w-20 rounded-full bg-muted" />
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-32 rounded bg-muted" />
                  <div className="h-3 w-3 rounded bg-muted" />
                  <div className="h-3 w-24 rounded bg-muted" />
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-7 w-28 rounded-md bg-muted" />
                  <div className="h-7 w-16 rounded-md bg-muted ml-auto" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-destructive">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="h-5 w-5" />
            <h2 className="text-lg font-semibold">Ошибка загрузки</h2>
          </div>
          <p className="mb-4">{(error as Error).message}</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-1 h-4 w-4" /> Повторить
          </Button>
        </div>
      ) : items.length === 0 && !hasActiveFilter ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <Network className="h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Нет сетей</h2>
          <p className="text-muted-foreground text-center max-w-sm">
            Сети не обнаружены. Запустите scan-networks или дождитесь следующего пайплайна.
          </p>
        </div>
      ) : items.length === 0 && hasActiveFilter ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <AlertCircle className="h-12 w-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Ничего не найдено</h2>
          <p className="text-muted-foreground text-center max-w-sm">
            По текущим фильтрам нет сетей. Попробуйте уменьшить минимальное количество филиалов или сбросить тип.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {items.map((net) => (
            <NetworkCard key={net.group_id} net={net} />
          ))}
        </div>
      )}
    </div>
  );
}
