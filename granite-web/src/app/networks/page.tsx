'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchNetworks, NetworksParams } from '@/lib/api/networks';
import { NetworkSummary } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Loader2, AlertCircle, Globe, Phone, Mail,
  MapPin, Building2, Star, RefreshCw,
  CheckCircle2, Clock, Network,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

const NETWORK_TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  franchise: { label: 'Франчайзинг', className: 'bg-[var(--network-franchise-bg)] text-[var(--network-franchise-text)] border-[var(--network-franchise-text)]/20' },
  aggregator: { label: 'Агрегатор', className: 'bg-[var(--network-aggregator-bg)] text-[var(--network-aggregator-text)] border-[var(--network-aggregator-text)]/20' },
  regional: { label: 'Региональная', className: 'bg-[var(--network-regional-bg)] text-[var(--network-regional-text)] border-[var(--network-regional-text)]/20' },
  local: { label: 'Локальная', className: 'bg-[var(--network-local-bg)] text-[var(--network-local-text)] border-[var(--network-local-text)]/20' },
};

const SIGNAL_CONFIG: Record<string, { label: string; icon: React.ElementType; className: string }> = {
  website: { label: 'сайт', icon: Globe, className: 'bg-primary/10 text-primary' },
  phone: { label: 'тел', icon: Phone, className: 'bg-amber-100 text-amber-700' },
  email_domain: { label: 'email', icon: Mail, className: 'bg-emerald-100 text-emerald-700' },
};

const CONTACT_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  none: { label: 'Не отправлено', className: 'bg-[var(--contact-none-bg)] text-[var(--contact-none-text)]' },
  sent: { label: 'Отправлено', className: 'bg-[var(--contact-sent-bg)] text-[var(--contact-sent-text)]' },
};

const SEGMENT_COLORS: Record<string, string> = {
  A: 'bg-[var(--segment-a-bg)] text-white',
  B: 'bg-[var(--segment-b-bg)] text-white',
  C: 'bg-[var(--segment-c-bg)] text-white',
  D: 'bg-[var(--segment-d-bg)] text-gray-600',
  spam: 'bg-[var(--segment-spam-bg)] text-gray-400',
};

function SegmentBadge({ segment, count }: { segment: string; count: number }) {
  const cls = SEGMENT_COLORS[segment] ?? 'bg-gray-100 text-gray-500';
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>
      {segment} {count}
    </span>
  );
}

function NetworkCard({ net }: { net: NetworkSummary }) {
  const typeCfg = NETWORK_TYPE_CONFIG[net.network_type] ?? NETWORK_TYPE_CONFIG.franchise;
  const signalCfg = SIGNAL_CONFIG[net.signal_type] ?? SIGNAL_CONFIG.website;
  const statusCfg = CONTACT_STATUS_CONFIG[net.contact_status] ?? CONTACT_STATUS_CONFIG.none;
  const SignalIcon = signalCfg.icon;
  const topCities = net.top_cities.slice(0, 4);
  const isFranchise = net.network_type === 'franchise';
  const hasContact = Boolean(net.primary_email);
  const segments = Object.entries(net.segment_dist ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <Link href={`/networks/${encodeURIComponent(net.group_id)}`}>
      <div className="flex items-start gap-4 px-5 py-3.5 rounded-xl border bg-card hover:shadow-md transition-shadow cursor-pointer">
        <div className="flex flex-col items-center gap-1 pt-1 min-w-[64px]">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${typeCfg.className}`}>
            {typeCfg.label}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <span className="text-sm font-semibold font-mono truncate">{net.signal_value}</span>
            <Badge variant="outline" size="sm" className={signalCfg.className}>
              <SignalIcon className="h-3 w-3 mr-1" />
              {signalCfg.label}
            </Badge>
            {net.primary_email && (
              <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                {net.primary_email}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-1">
            <span className="flex items-center gap-1"><Building2 className="h-3 w-3" /> {net.company_count}</span>
            <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {net.city_count} гор.</span>
            <span className="flex items-center gap-1"><Star className="h-3 w-3" /> {net.avg_score.toFixed(1)}</span>
          </div>

          {segments.length > 0 && (
            <div className="flex items-center gap-1 text-[10px] mt-1">
              {segments.map(([seg, count]) => (
                <SegmentBadge key={seg} segment={seg} count={count} />
              ))}
            </div>
          )}

          {topCities.length > 0 && (
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground mt-1 flex-wrap">
              {topCities.map((c, i) => (
                <span key={c.name} className="flex items-center gap-0.5">
                  {c.name} ({c.count})
                  {i < topCities.length - 1 && <span className="text-gray-300">·</span>}
                </span>
              ))}
              {net.top_cities.length > 4 && <span className="opacity-50">+{net.top_cities.length - 4}</span>}
            </div>
          )}
        </div>

        <div className="flex flex-col items-end gap-1.5 shrink-0 min-w-[100px]">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${statusCfg.className}`}>
            {net.contact_status === 'none' && <Clock className="h-3 w-3 inline mr-0.5" />}
            {net.contact_status === 'sent' && <CheckCircle2 className="h-3 w-3 inline mr-0.5" />}
            {statusCfg.label}
          </span>
          {isFranchise && net.total_count > 0 && (
            <span className="text-[10px] text-muted-foreground">
              {net.sent_count}/{net.total_count}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-7"
            disabled={!hasContact}
            aria-label={isFranchise ? 'Выбрать филиалы для кампании' : 'Добавить сеть в кампанию'}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            {isFranchise ? 'Выбрать филиалы' : '+ В кампанию'}
          </Button>
        </div>
      </div>
    </Link>
  );
}

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
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-3.5 rounded-xl border bg-card animate-pulse">
              <div className="h-8 w-16 rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-48 rounded bg-muted" />
                <div className="h-3 w-72 rounded bg-muted" />
              </div>
              <div className="flex gap-2">
                <div className="h-6 w-20 rounded-md bg-muted" />
                <div className="h-6 w-24 rounded-md bg-muted" />
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
        <div className="space-y-2">
          {items.map((net) => (
            <NetworkCard key={net.group_id} net={net} />
          ))}
        </div>
      )}
    </div>
  );
}
