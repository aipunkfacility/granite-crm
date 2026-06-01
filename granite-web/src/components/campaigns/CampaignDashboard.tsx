'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCampaignDetail, fetchABStats, fetchRecipients, removeRecipients, type ABStats, type CampaignStatus, type RecipientItem } from '@/lib/api/campaigns';
import { apiClient } from '@/lib/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Play,
  Pause,
  CheckCircle2,
  Users,
  BarChart2,
  Mail,
  AlertTriangle,
  Loader2,
  FlaskConical,
  Clock,
  Zap,
  ArrowLeft,
  X as XIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface DashboardProps {
  campaignId: number;
  onClose: () => void;
}

// P4R-L17: Единая константа для API URL
function getApiBaseUrl(): string {
  return (apiClient.defaults.baseURL || '').replace(/\/$/, '');
}

export function CampaignDashboard({ campaignId, onClose }: DashboardProps) {
  const [liveProgress, setLiveProgress] = useState<{
    status: string;
    sent: number;
    total: number;
    errors: number;
  } | null>(null);

  // P4R-M18: abStats типизирован как ABStats | null вместо any
  const [abStats, setAbStats] = useState<ABStats | null>(null);
  const [abStatsError, setAbStatsError] = useState<string | null>(null);  // P4R-M19
  const eventSourceRef = useRef<EventSource | null>(null);
  const prevStatusRef = useRef<string | null>(null);
  // P4R-H5: Реф для exponential backoff при SSE реконнекте
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Загрузка деталей кампании
  const { data: campaign, isLoading, refetch } = useQuery({
    queryKey: ['campaign-detail', campaignId],
    queryFn: () => fetchCampaignDetail(campaignId),
    refetchInterval: (query) => {
      return query.state.data?.status === 'running' ? 3000 : 15000;
    },
  });

  // Загрузка A/B статистики
  useEffect(() => {
    if (campaign?.subject_b) {
      setAbStatsError(null);
      fetchABStats(campaignId)
        .then(setAbStats)
        .catch((err) => {
          // P4R-M19: Показываем ошибку вместо молчаливого проглатывания
          setAbStatsError(err?.message || 'Не удалось загрузить A/B статистику');
        });
    }
  }, [campaignId, campaign?.subject_b]);

  // P4R-H4: Получение auth-токена для SSE (query param).
  // EventSource не поддерживает кастомные заголовки, поэтому передаём
  // токен через URL. Пока auth не реализован — токен пустой.
  const getSSEToken = useCallback((): string => {
    return process.env.NEXT_PUBLIC_API_KEY || '';
  }, []);

  // P4R-H5: Подключение к SSE с exponential backoff
  const connectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const baseUrl = getApiBaseUrl();
    const token = getSSEToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const es = new EventSource(`${baseUrl}/campaigns/${campaignId}/progress${tokenParam}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLiveProgress(data);
        // Успешное сообщение — сбрасываем retry counter
        retryCountRef.current = 0;
        // Если кампания завершилась — обновляем данные
        if (data.status === 'completed' || data.status === 'paused' || data.status === 'paused_daily_limit') {
          refetch();
          es.close();
          eventSourceRef.current = null;
        }
      } catch {}
    };

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;

      // P4R-H5: Exponential backoff — 1s → 2s → 4s → 8s → 16s → 30s max
      const maxDelay = 30000;
      const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), maxDelay);
      retryCountRef.current += 1;

      // Проверяем, что кампания всё ещё running перед реконнектом
      if (campaign?.status === 'running') {
        retryTimerRef.current = setTimeout(() => {
          connectSSE();
        }, delay);
      } else {
        // Не running — просто обновляем через polling
        refetch();
      }
    };
  }, [campaignId, campaign?.status, getSSEToken, refetch]);

  // SSE live-прогресс — подключаемся только при status=running
  useEffect(() => {
    const prevStatus = prevStatusRef.current;
    prevStatusRef.current = campaign?.status || null;

    if (!campaign || campaign.status !== 'running') {
      // Закрываем SSE если кампания не запущена
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      // Очищаем таймер реконнекта
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      retryCountRef.current = 0;
      return;
    }

    // Переподключаемся только при смене статуса на running
    if (prevStatus === 'running') return;

    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
    // P4R-L6: refetch стабилен от React Query, connectSSE зависит от нужных значений
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, campaign?.status, connectSSE]);

  if (isLoading || !campaign) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const progress = liveProgress 
    ? (liveProgress.total > 0 ? Math.round((liveProgress.sent / liveProgress.total) * 100) : 0)
    : (campaign.preview_recipients > 0 ? Math.round((campaign.total_sent / campaign.preview_recipients) * 100) : 0);

  const currentSent = liveProgress?.sent ?? campaign.total_sent;
  const currentTotal = liveProgress?.total ?? campaign.preview_recipients;
  const currentErrors = liveProgress?.errors ?? campaign.total_errors;

  const isRunning = campaign.status === 'running';
  const hasAB = !!(campaign.subject_a && campaign.subject_b);
  const isPausedDailyLimit = campaign.status === 'paused_daily_limit';

  const replyRate = campaign.total_sent > 0
    ? Math.round((campaign.total_replied / campaign.total_sent) * 100)
    : 0;

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      {/* ===== LEFT PANEL ===== */}
      <div className="flex-1 min-w-0">
        {/* Sticky header */}
        <div className="sticky top-0 z-10 bg-background pb-4">
          <div className="flex items-center gap-3 pt-1">
            <Button variant="ghost" size="icon" className="-ml-2 h-8 w-8" onClick={onClose}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <h2 className="text-xl font-bold truncate">{campaign.name}</h2>
            <Badge
              variant={isRunning ? 'default' : 'outline'}
              className={cn('flex items-center gap-1.5 px-3 py-1 shrink-0', isRunning && 'animate-pulse')}
            >
              {isRunning ? (
                <><Play className="h-3 w-3" /> Запущена</>
              ) : campaign.status === 'completed' ? (
                <><CheckCircle2 className="h-3 w-3" /> Завершена</>
              ) : (
                <><Pause className="h-3 w-3" /> {isPausedDailyLimit ? 'Дневной лимит' : 'Пауза'}</>
              )}
            </Badge>
          </div>
        </div>

        <div className="space-y-6">
          {/* Validator warnings */}
          {campaign.validator_warnings?.length > 0 && campaign.status === 'draft' && (
            <div className="space-y-2">
              {campaign.validator_warnings.map((w, i) => (
                <div key={i} className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950/20 dark:border-amber-800">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <p className="text-sm text-amber-800 dark:text-amber-200">{w}</p>
                </div>
              ))}
            </div>
          )}

          {/* Фильтры кампании (только для filter-режима) */}
          {campaign.recipient_mode === 'filter' && (
            <Card className="border-border">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Фильтры
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg bg-muted">
                    <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Город</p>
                    <p className="font-medium">{campaign.filters?.city || 'Все'}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted">
                    <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Сегмент</p>
                    <p className="font-medium">{campaign.filters?.segment || 'Все'}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted">
                    <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Мин. скор</p>
                    <p className="font-medium">{campaign.filters?.min_score || '0'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Получатели (для manual-режима) — в потоке */}
          {campaign.recipient_mode === 'manual' && (
            <CampaignRecipientsSection campaignId={campaignId} recipientCount={campaign.recipient_count ?? 0} />
          )}
        </div>
      </div>

      {/* ===== RIGHT PANEL (sticky) ===== */}
      <div className="w-72 shrink-0 sticky top-6 space-y-6">
        {/* Ход рассылки — прогресс-бар на ширину панели */}
        <Card className="border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              {isRunning ? <Zap className="h-4 w-4 text-primary animate-pulse" /> : <Mail className="h-4 w-4" />}
              Ход рассылки
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Progress value={progress} className="h-2" />
              <div className="flex justify-between text-[11px] text-muted-foreground">
                <span>Отправлено: {currentSent}</span>
                <span>Всего: {currentTotal}</span>
              </div>
              <p className="text-right text-lg font-bold">{progress}%</p>
            </div>
          </CardContent>
        </Card>

        {/* Причина паузы — под ходом рассылки */}
        {isPausedDailyLimit && (
          <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950/20 dark:border-amber-800">
            <Clock className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-sm text-amber-800 dark:text-amber-200">Достигнут дневной лимит отправки</p>
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                Кампания приостановлена автоматически. Продолжите отправку завтра или измените EMAIL_DAILY_LIMIT.
              </p>
            </div>
          </div>
        )}

        {/* Статистика — вертикально */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart2 className="h-5 w-5" />
              Статистика
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              <div className="flex justify-between items-baseline">
                <span className="text-base text-muted-foreground">Отправлено</span>
                <span className="text-2xl font-bold">{currentSent}</span>
              </div>
              <div className="flex justify-between items-baseline">
                <span className="text-base text-muted-foreground">Открыто</span>
                <span className="text-2xl font-bold text-success">{campaign.total_opened} <span className="text-lg text-success/70">({campaign.open_rate}%)</span></span>
              </div>
              <div className="flex justify-between items-baseline">
                <span className="text-base text-muted-foreground">Ответов</span>
                <span className="text-2xl font-bold text-primary">{campaign.total_replied}</span>
              </div>
              <div className="flex justify-between items-baseline">
                <span className="text-base text-muted-foreground">Ошибок</span>
                <span className="text-2xl font-bold text-destructive">{currentErrors}</span>
              </div>
              <div className="pt-5 border-t space-y-4">
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-muted-foreground">Open Rate</span>
                  <span className="text-lg font-bold text-success">{campaign.open_rate}%</span>
                </div>
                <div className="flex justify-between items-baseline">
                  <span className="text-sm text-muted-foreground">Reply Rate</span>
                  <span className="text-lg font-bold text-primary">{replyRate}%</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* A/B Сравнение — вертикально */}
        {hasAB && abStats && abStats.variants && Object.keys(abStats.variants).length > 0 && (
          <Card className="border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-primary" />
                A/B Сравнение
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(abStats.variants).map(([variant, variantData]) => (
                  <div key={variant} className={cn(
                    'p-3 rounded-xl border-2',
                    variant === 'A' ? 'border-blue-300 bg-blue-50 dark:bg-blue-950/20' : 'border-purple-300 bg-purple-50 dark:bg-purple-950/20'
                  )}>
                    <Badge variant="outline" className={cn(
                      'text-[10px] px-1.5 py-0 mb-2',
                      variant === 'A' ? 'border-blue-400 text-blue-700' : 'border-purple-400 text-purple-700'
                    )}>
                      Вариант {variant}
                    </Badge>
                    <p className="text-[11px] text-muted-foreground mb-2 line-clamp-2">{variantData.subject}</p>
                    <div className="grid grid-cols-3 gap-1 text-center mb-2">
                      <div>
                        <p className="text-sm font-bold">{variantData.sent}</p>
                        <p className="text-[8px] uppercase text-muted-foreground">Отпр</p>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-success">{variantData.opened}</p>
                        <p className="text-[8px] uppercase text-muted-foreground">Откр</p>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-primary">{variantData.replied}</p>
                        <p className="text-[8px] uppercase text-muted-foreground">Отв</p>
                      </div>
                    </div>
                    <div className="text-center pt-2 border-t">
                      <p className="text-xs font-bold text-primary">{variantData.reply_rate}% Reply Rate</p>
                    </div>
                  </div>
                ))}
              </div>
              {abStats.winner && (
                <p className="mt-3 text-xs text-muted-foreground text-center">
                  Победитель: <strong className={abStats.winner === 'B' ? 'text-purple-700' : 'text-blue-700'}>{abStats.winner}</strong>
                </p>
              )}
              {abStats.note && (
                <p className="mt-1 text-[10px] text-muted-foreground text-center">{abStats.note}</p>
              )}
            </CardContent>
          </Card>
        )}

        {/* P4R-M19: Ошибка загрузки A/B статистики */}
        {hasAB && abStatsError && !abStats && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/5 border border-destructive/20">
            <AlertTriangle className="h-4 w-4 text-destructive shrink-0" />
            <p className="text-sm text-destructive">{abStatsError}</p>
          </div>
        )}
      </div>
    </div>
  );
}

/** Секция получателей для manual-кампаний. */
function CampaignRecipientsSection({ campaignId, recipientCount }: { campaignId: number; recipientCount: number }) {
  const [page, setPage] = useState(1);
  const perPage = 20;

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['campaign-recipients', campaignId, page],
    queryFn: () => fetchRecipients(campaignId, page, perPage),
  });

  const handleRemove = async (companyId: number) => {
    try {
      await removeRecipients(campaignId, [companyId]);
      refetch();
      toast.success('Компания удалена из кампании');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const items: RecipientItem[] = data?.items ?? [];
  const total: number = data?.total ?? 0;

  const statusConfig: Record<string, { label: string; className: string }> = {
    pending: { label: 'В очереди', className: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
    sent: { label: 'Отправлено', className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
    opened: { label: 'Открыто', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
    replied: { label: 'Ответили', className: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
    bounced: { label: 'Не доставлено', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
    failed: { label: 'Ошибка отправки', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  };

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Mail className="h-5 w-5" />
          Получатели
          <Badge variant="outline" className="ml-2 text-xs">{recipientCount} компаний</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">
            Нет добавленных компаний. Добавьте компании через карточку компании или массовый выбор.
          </p>
        ) : (
          <>
            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.id} className="flex items-center gap-3 p-2.5 rounded-lg border border-border hover:bg-muted/50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.city}{item.segment ? ` · ${item.segment}` : ''}{item.crm_score ? ` · Score: ${item.crm_score}` : ''}
                    </p>
                  </div>
                  <div className="text-xs text-muted-foreground truncate max-w-[180px]">
                    {item.emails?.[0] || '—'}
                  </div>
                  {(() => {
                    const cfg = item.send_status ? statusConfig[item.send_status] : undefined;
                    return cfg ? (
                      <Badge variant="outline" size="sm" className={cn('uppercase tracking-wide', cfg.className)}>
                        {cfg.label}
                      </Badge>
                    ) : (
                      <Badge variant="outline" size="sm" className="uppercase tracking-wide text-muted-foreground">
                        Не отправлено
                      </Badge>
                    );
                  })()}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive shrink-0"
                    onClick={() => handleRemove(item.id)}
                    title="Удалить из кампании"
                  >
                    <XIcon className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
            {/* Пагинация */}
            {total > perPage && (
              <div className="flex items-center justify-between pt-4 border-t mt-4">
                <p className="text-xs text-muted-foreground">
                  Страница {page} из {Math.ceil(total / perPage)} · Всего {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Назад
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page * perPage >= total}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Далее
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
