'use client';

import React, { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNetworkCandidates, NetworkCandidatesParams } from '@/lib/api/networks';
import { NetworkGroupCard } from '@/components/networks/NetworkGroupCard';
import { NetworkCandidateGroup } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
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
import { useRouter } from 'next/navigation';

const SECTION_LABELS: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  email_domain: { label: 'Email-домен', icon: Mail, color: 'bg-success/10 text-success' },
  website: { label: 'Сайт', icon: Globe, color: 'bg-primary/10 text-primary' },
  phone: { label: 'Телефон', icon: Phone, color: 'bg-warning/10 text-warning' },
};

type SignalType = '' | 'email_domain' | 'website' | 'phone';

export default function NetworkCandidatesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [signalFilter, setSignalFilter] = useState<SignalType>('');
  const [minCompanies, setMinCompanies] = useState(3);
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['email_domain', 'website', 'phone']));

  const params: NetworkCandidatesParams = { include_resolved: true };
  if (signalFilter) params.signal_type = signalFilter;
  if (minCompanies > 2) params.min_companies = minCompanies;

  const { data, isLoading, error } = useQuery({
    queryKey: ['network-candidates', 'all', params],
    queryFn: () => fetchNetworkCandidates(params),
    staleTime: 10_000,
  });

  const allGroups = data?.groups ?? [];

  const waitingGroups = useMemo(
    () => allGroups.filter((g) => !g.all_marked),
    [allGroups],
  );
  const resolvedGroups = useMemo(
    () => allGroups.filter((g) => g.all_marked),
    [allGroups],
  );

  const groupedWaiting = useMemo(() => {
    const map = new Map<string, NetworkCandidateGroup[]>();
    for (const g of waitingGroups) {
      const list = map.get(g.signal_type) ?? [];
      list.push(g);
      map.set(g.signal_type, list);
    }
    return map;
  }, [waitingGroups]);

  const groupedResolved = useMemo(() => {
    const map = new Map<string, NetworkCandidateGroup[]>();
    for (const g of resolvedGroups) {
      const list = map.get(g.signal_type) ?? [];
      list.push(g);
      map.set(g.signal_type, list);
    }
    return map;
  }, [resolvedGroups]);

  const handleResolved = () => {
    queryClient.invalidateQueries({ queryKey: ['network-candidates', 'all'] });
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

  const totalWaiting = waitingGroups.length;
  const totalResolved = resolvedGroups.length;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => router.push('/networks')} className="mb-2">
        <ArrowLeft className="mr-1 h-4 w-4" /> К списку сетей
      </Button>

      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground flex items-center gap-3">
          <GitBranch className="h-8 w-8 text-warning" />
          Кандидаты на разметку
          {totalWaiting > 0 && (
            <Badge variant="default" className="text-sm px-2.5 py-0.5" style={{ background: 'rgba(196,144,8,0.15)', color: 'var(--warning)' }}>
              {totalWaiting} ждут
            </Badge>
          )}
          {totalResolved > 0 && (
            <Badge variant="outline" size="sm" className="text-xs">{totalResolved} размечены</Badge>
          )}
        </h1>
        <p className="text-sm text-muted-foreground">
          Группы компаний, объединённые общим сайтом, доменом email или телефоном.
          Разметка сети объединяет их под одной сетью; дубли сливаются в одну запись.
        </p>
      </div>

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
      </div>

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
      ) : waitingGroups.length === 0 && resolvedGroups.length === 0 ? (
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
            const sectionGroups = groupedWaiting.get(st) ?? [];
            const sectionResolved = groupedResolved.get(st) ?? [];
            if (sectionGroups.length === 0 && sectionResolved.length === 0) return null;
            const cfg = SECTION_LABELS[st];
            const Icon = cfg.icon;
            const isOpen = openSections.has(st);
            return (
              <div key={st} className="rounded-xl border bg-card">
                <button
                  onClick={() => toggleSection(st)}
                  aria-expanded={isOpen}
                  aria-controls={st + '-content'}
                  className="flex items-center justify-between w-full px-5 py-3 text-left hover:bg-muted/50 transition-colors rounded-t-xl"
                >
                  <div className="flex items-center gap-2">
                    <div className={`flex h-7 w-7 items-center justify-center rounded-md ${cfg.color}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="font-medium">{cfg.label}</span>
                    {sectionGroups.length > 0 && (
                      <Badge variant="outline" size="sm" style={{ borderColor: 'rgba(196,144,8,0.3)', color: 'var(--warning)' }}>
                        {sectionGroups.length} ждут
                      </Badge>
                    )}
                    {sectionResolved.length > 0 && (
                      <Badge variant="outline" size="sm" style={{ borderColor: 'rgba(91,106,191,0.3)', color: 'var(--primary)' }}>
                        ✓ {sectionResolved.length} размечены
                      </Badge>
                    )}
                  </div>
                  {isOpen ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
                {isOpen && (
                  <div id={st + '-content'} className="px-5 pb-5 pt-2 space-y-4">
                    {sectionGroups.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-3">
                          <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-warning/20 text-warning text-[9px] font-bold">
                            {sectionGroups.length}
                          </span>
                          Ждут разметки
                        </h4>
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
                    {sectionResolved.length > 0 && (
                      <div className={sectionGroups.length > 0 ? 'border-t border-border pt-4' : ''}>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-3">
                          <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-primary/20 text-primary text-[9px] font-bold">
                            ✓
                          </span>
                          Размечены
                        </h4>
                        <div className="space-y-1 max-h-80 overflow-y-auto">
                          {sectionResolved.map((group) => (
                            <div key={group.group_id} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-muted/30 text-sm">
                              <div className={`flex h-6 w-6 items-center justify-center rounded-md ${cfg.color}`}>
                                <Icon className="h-3 w-3" />
                              </div>
                              <span className="font-mono text-xs font-medium">{group.signal_value}</span>
                              <Badge variant="outline" size="sm" className="font-mono">{group.company_count} компаний</Badge>
                              <Badge variant="default" size="sm" className="ml-auto">Сеть</Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
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
