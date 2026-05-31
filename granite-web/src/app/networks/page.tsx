'use client';

import React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchNetworkCandidates } from '@/lib/api/networks';
import { NetworkGroupCard } from '@/components/networks/NetworkGroupCard';
import { Badge } from '@/components/ui/badge';
import {
  GitBranch,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

export default function NetworksPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['network-candidates'],
    queryFn: fetchNetworkCandidates,
    staleTime: 10_000,
  });

  const groups = data?.groups ?? [];
  const total = data?.total ?? 0;

  const handleResolved = () => {
    queryClient.invalidateQueries({ queryKey: ['network-candidates'] });
    queryClient.invalidateQueries({ queryKey: ['companies'] });
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
        <div className="grid gap-4 md:grid-cols-2">
          {groups.map((group) => (
            <NetworkGroupCard
              key={group.group_id}
              group={group}
              onResolved={handleResolved}
            />
          ))}
        </div>
      )}
    </div>
  );
}
