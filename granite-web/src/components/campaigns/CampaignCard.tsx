'use client';

import { type Campaign, type CampaignStatus } from '@/lib/api/campaigns';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Play,
  Pause,
  CheckCircle2,
  Clock,
  Trash2,
  Loader2,
  LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { badgeVariants } from '@/components/ui/badge';

type BadgeVariant = NonNullable<Parameters<typeof badgeVariants>[0]>['variant'];

interface StatusConfig {
  label: string;
  variant: NonNullable<BadgeVariant>;
  icon: LucideIcon;
}

const STATUS_CONFIG: Record<CampaignStatus, StatusConfig> = {
  draft: { label: 'Черновик', variant: 'secondary', icon: Clock },
  running: { label: 'Запущена', variant: 'default', icon: Play },
  paused: { label: 'Пауза', variant: 'outline', icon: Pause },
  paused_daily_limit: { label: 'Лимит', variant: 'outline', icon: Pause },
  completed: { label: 'Завершена', variant: 'success', icon: CheckCircle2 },
};

interface CampaignCardProps {
  campaign: Campaign;
  onOpenDashboard: () => void;
  onRun: () => void;
  onPause: () => void;
  onDelete: () => void;
  isRunning: boolean;
  isPausing: boolean;
  deleteConfirmActive: boolean;
  onRequestDeleteConfirm: () => void;
  onCancelDeleteConfirm: () => void;
}

export function CampaignCard({
  campaign,
  onOpenDashboard,
  onRun,
  onPause,
  onDelete,
  isRunning,
  isPausing,
  deleteConfirmActive,
  onRequestDeleteConfirm,
  onCancelDeleteConfirm,
}: CampaignCardProps) {
  const status = STATUS_CONFIG[campaign.status] || STATUS_CONFIG.draft;
  const totalTargets = campaign.total_recipients ?? campaign.total_sent ?? 0;
  const progress = totalTargets > 0
    ? Math.round((campaign.total_sent / totalTargets) * 100)
    : 0;
  const openRate = campaign.total_sent > 0
    ? Math.round((campaign.total_opened / campaign.total_sent) * 100)
    : 0;
  const hasAB = !!(campaign.subject_a && campaign.subject_b);

  return (
    <Card className="overflow-hidden border-border hover:shadow-md transition-shadow">
      <CardHeader className="border-b bg-muted/50 py-3 px-6 flex flex-row items-stretch justify-between space-y-0 gap-6">
        <div className="flex flex-col justify-center space-y-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="text-lg font-bold cursor-pointer hover:text-primary truncate"
              onClick={onOpenDashboard}
            >
              {campaign.name}
            </span>
            <Badge variant={status.variant} className="flex items-center gap-1.5 px-2.5 py-0.5 shrink-0">
              <status.icon className={cn('h-3 w-3', campaign.status === 'running' && 'animate-pulse')} />
              {status.label}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-xs text-muted-foreground">
              Шаблон: <span className="font-mono text-primary">{campaign.template_name}</span>
            </p>
            {hasAB && (
              <Badge variant="outline" size="sm" className="bg-primary/10 text-primary border-primary/20">
                A/B тест
              </Badge>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm shrink-0">
          <span className="text-foreground font-medium">Охват: {campaign.total_sent}</span>
          <span className="text-muted-foreground">·</span>
          <span className="text-success font-medium">Открыто: {campaign.total_opened} ({openRate}%)</span>
          <span className="text-muted-foreground">·</span>
          <span className="text-primary font-medium">Ответов: {campaign.total_replied}</span>
          <span className="text-muted-foreground">·</span>
          <span className="text-destructive font-medium">Ошибок: {campaign.total_errors || 0}</span>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <div className="flex items-center gap-3">
          {['draft', 'paused', 'paused_daily_limit', 'completed'].includes(campaign.status) ? (
            <Button
              className="shrink-0 bg-success hover:bg-success/90 text-success-foreground h-9"
              onClick={onRun}
              disabled={isRunning}
            >
              {isRunning ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Запуск...</>
              ) : (
                <><Play className="mr-2 h-4 w-4 fill-current" /> Запустить</>
              )}
            </Button>
          ) : campaign.status === 'running' ? (
            <Button
              variant="outline"
              className="shrink-0 h-9"
              onClick={onPause}
              disabled={isPausing}
            >
              {isPausing ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Приостановка...</>
              ) : (
                <><Pause className="mr-2 h-4 w-4" /> Пауза</>
              )}
            </Button>
          ) : null}

          <div className="flex-1 space-y-1">
            <Progress value={progress} className="h-2" />
            <div className="flex justify-between text-[11px] text-muted-foreground">
              <span>Отправлено: {campaign.total_sent}</span>
              <span>Всего: {totalTargets}</span>
            </div>
          </div>

          {campaign.status === 'draft' && (
            <>
              {deleteConfirmActive ? (
                <div className="flex gap-1 shrink-0">
                  <Button
                    variant="destructive"
                    size="sm"
                    className="h-9 text-xs"
                    onClick={onDelete}
                  >
                    Да
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 text-xs"
                    onClick={onCancelDeleteConfirm}
                  >
                    Нет
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={onRequestDeleteConfirm}
                  title="Удалить черновик"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
