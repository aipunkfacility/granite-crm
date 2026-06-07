'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchNetworks, NetworksParams } from '@/lib/api/networks';
import { NetworkSummary } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { GitBranch, Loader2, AlertCircle, Globe, Phone, Mail, MapPin, Building2, Star, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

const SIGNAL_LABELS: Record<string, { label: string; icon: React.ElementType; className: string }> = {
  website: { label: 'Сайт', icon: Globe, className: 'bg-primary/10 text-primary' },
  phone: { label: 'Телефон', icon: Phone, className: 'bg-warning/10 text-warning' },
  email_domain: { label: 'Email', icon: Mail, className: 'bg-success/10 text-success' },
};

function NetworkCard({ net }: { net: NetworkSummary }) {
  const cfg = SIGNAL_LABELS[net.signal_type] ?? SIGNAL_LABELS.website;
  const Icon = cfg.icon;
  const topCities = net.top_cities.slice(0, 4);
  const maxCount = net.top_cities[0]?.count ?? 1;

  return (
    <Link href={`/networks/${encodeURIComponent(net.group_id)}`}>
      <div className="flex items-center gap-4 px-5 py-3.5 rounded-xl border bg-card hover:shadow-md transition-shadow cursor-pointer">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${cfg.className}`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-semibold font-mono truncate">{net.signal_value}</span>
            <Badge variant="outline" size="sm">{cfg.label}</Badge>
          </div>
          {topCities.length > 0 ? (
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
              {topCities.map((c, i) => (
                <span key={c.name} className="flex items-center gap-1">
                  <span
                    className="inline-block h-1 rounded-sm"
                    style={{ width: 16 + (c.count / maxCount) * 20, background: 'var(--primary)', opacity: 0.3 + (1 - i / topCities.length) * 0.5 }}
                  />
                  {c.name} ({c.count})
                </span>
              ))}
              {net.top_cities.length > 4 && <span className="opacity-50">+{net.top_cities.length - 4}</span>}
            </div>
          ) : (
            <span className="text-[11px] text-muted-foreground">Нет данных о городах</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/50 text-xs font-medium">
            <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono">{net.company_count}</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/50 text-xs font-medium">
            <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono">{net.city_count}</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/50 text-xs font-medium">
            <Star className={`h-3.5 w-3.5 ${net.avg_score >= 4.5 ? 'text-success' : 'text-muted-foreground'}`} />
            <span className={`font-mono ${net.avg_score >= 4.5 ? 'text-success' : ''}`}>{net.avg_score.toFixed(1)}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export default function NetworksPage() {
  const router = useRouter();
  const [signalFilter, setSignalFilter] = useState<string>('');
  const [minCompanies, setMinCompanies] = useState(2);
  const params: NetworksParams = {};
  if (signalFilter) params.signal_type = signalFilter;
  if (minCompanies > 2) params.min_companies = minCompanies;

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['networks', params],
    queryFn: () => fetchNetworks(params),
    staleTime: 10_000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasActiveFilter = signalFilter !== '' || minCompanies > 2;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <GitBranch className="h-8 w-8 text-primary" />
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
          value={signalFilter}
          onChange={(e) => setSignalFilter(e.target.value)}
        >
          <option value="">Все типы</option>
          <option value="website">Сайт</option>
          <option value="phone">Телефон</option>
          <option value="email_domain">Email-домен</option>
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
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-3.5 rounded-xl border bg-card animate-pulse">
              <div className="h-8 w-8 rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-48 rounded bg-muted" />
                <div className="h-3 w-72 rounded bg-muted" />
              </div>
              <div className="flex gap-2">
                <div className="h-6 w-12 rounded-md bg-muted" />
                <div className="h-6 w-12 rounded-md bg-muted" />
                <div className="h-6 w-12 rounded-md bg-muted" />
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
          <GitBranch className="h-12 w-12 text-muted-foreground" />
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
            По текущим фильтрам нет сетей. Попробуйте уменьшить минимальное количество филиалов или сбросить тип сигнала.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((net) => (
            <NetworkCard key={net.group_id} net={net} />
          ))}
        </div>
      )}
    </div>
  );
}
