'use client';

import React, { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNetworkCandidates, NetworkCandidatesParams } from '@/lib/api/networks';
import { NetworkGroupCard } from '@/components/networks/NetworkGroupCard';
import { NetworkCandidateGroup } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import {
  GitBranch,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Mail,
  Globe,
  Phone,
} from 'lucide-react';

const SECTION_LABELS: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  email_domain: { label: 'Email-домен', icon: Mail, color: 'bg-blue-500/10 text-blue-600' },
  website: { label: 'Сайт', icon: Globe, color: 'bg-green-500/10 text-green-600' },
  phone: { label: 'Телефон', icon: Phone, color: 'bg-orange-500/10 text-orange-600' },
};

type SignalType = '' | 'email_domain' | 'website' | 'phone';

export default function NetworksPage() {
  const queryClient = useQueryClient();

  const [signalFilter, setSignalFilter] = useState<SignalType>('');
  const [minCompanies, setMinCompanies] = useState(3);
  const [includeResolved, setIncludeResolved] = useState(false);
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['email_domain', 'website', 'phone']));

  const params: NetworkCandidatesParams = {};
  if (signalFilter) params.signal_type = signalFilter;
  if (minCompanies > 2) params.min_companies = minCompanies;
  if (includeResolved) params.include_resolved = true;

  const { data, isLoading, error } = useQuery({
    queryKey: ['network-candidates', params],
    queryFn: () => fetchNetworkCandidates(params),
    staleTime: 10_000,
  });

  const groups = data?.groups ?? [];
  const total = data?.total ?? 0;

  const grouped = useMemo(() => {
    const map = new Map<string, NetworkCandidateGroup[]>();
    for (const g of groups) {
      const list = map.get(g.signal_type) ?? [];
      list.push(g);
      map.set(g.signal_type, list);
    }
    return map;
  }, [groups]);

  const handleResolved = () => {
    queryClient.invalidateQueries({ queryKey: ['network-candidates'] });
    queryClient.invalidateQueries({ queryKey: ['companies'] });
  };

  const toggleSection = (key: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground flex items-center gap-3">
          <GitBranch className="h-8 w-8 text-primary" />
          Сети
          {total > 0 && (
            <Badge variant="default" className="text-sm px-2.5 py-0.5">
              {total}
            </Badge>
          )}
        </h1>
        <p className="text-sm text-muted-foreground">
          Группы компаний, объединённые общим сайтом, доменом email или телефоном.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 p-4 rounded-lg border bg-muted/30">
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={signalFilter}
          onChange={(e) => setSignalFilter(e.target.value as SignalType)}
        >
          <option value="">Все типы</option>
          <option value="email_domain">Email-домен</option>
          <option value="website">Сайт</option>
          <option value="phone">Телефон</option>
        </select>

        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Мин. компаний:</label>
          <input
            type="number"
            min={2}
            max={100}
            value={minCompanies}
            onChange={(e) => setMinCompanies(Number(e.target.value))}
            className="h-9 w-20 rounded-md border bg-background px-2 text-sm text-center"
          />
        </div>

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={includeResolved}
            onChange={(e) => setIncludeResolved(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          Включить размеченные
        </label>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <Loader2 className="h-10 w-10 text-primary animate-spin" />
          <p className="text-muted-foreground animate-pulse">Загрузка кандидатов...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-destructive">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="h-5 w-5" />
            <h2 className="text-lg font-semibold">Ошибка загрузки</h2>
          </div>
          <p>{(error as Error).message}</p>
        </div>
      ) : groups.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
            <CheckCircle2 className="h-8 w-8 text-success" />
          </div>
          <h2 className="text-xl font-semibold text-foreground">Нет кандидатов</h2>
          <p className="text-muted-foreground text-center max-w-sm">
            Все группы обработаны. Новые появятся после следующего запуска детектора сетей.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {['email_domain', 'website', 'phone'].map((st) => {
            const sectionGroups = grouped.get(st) ?? [];
            if (sectionGroups.length === 0) return null;
            const cfg = SECTION_LABELS[st];
            const Icon = cfg.icon;
            const isOpen = openSections.has(st);
            return (
              <div key={st} className="rounded-xl border bg-card">
                <button
                  onClick={() => toggleSection(st)}
                  className="flex items-center justify-between w-full px-5 py-3 text-left hover:bg-muted/50 transition-colors rounded-t-xl"
                >
                  <div className="flex items-center gap-2">
                    <div className={`flex h-7 w-7 items-center justify-center rounded-md ${cfg.color}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="font-medium">{cfg.label}</span>
                    <Badge variant="secondary" className="ml-1">{sectionGroups.length}</Badge>
                  </div>
                  {isOpen ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 pt-2">
                    <div className="grid gap-4 md:grid-cols-2">
                      {sectionGroups.map((group) => (
                        <NetworkGroupCard
                          key={group.group_id}
                          group={group}
                          onResolved={handleResolved}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
