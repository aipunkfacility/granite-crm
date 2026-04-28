'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCampaignDetail, fetchABStats, type ABStats, type CampaignStatus } from '@/lib/api/campaigns';
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
      const data = query.state.data;
      return data?.status === 'running' ? 3000 : 15000;
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
    // TODO: Заменить на реальный токен когда будет auth
    // Пример: return localStorage.getItem('auth_token') || '';
    return '';
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">{campaign.name}</h2>
          <p className="text-sm text-muted-foreground">
            Шаблон: <span className="font-mono text-primary">{campaign.template_name}</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge 
            variant={isRunning ? "default" : "outline"} 
            className={cn("flex items-center gap-1.5 px-3 py-1 text-sm", isRunning && "animate-pulse")}
          >
            {isRunning ? (
              <><Play className="h-3 w-3" /> Запущена</>
            ) : campaign.status === 'completed' ? (
              <><CheckCircle2 className="h-3 w-3" /> Завершена</>
            ) : (
              <><Pause className="h-3 w-3" /> {isPausedDailyLimit ? 'Дневной лимит' : 'Пауза'}</>
            )}
          </Badge>
          {hasAB && (
            <Badge variant="outline" className="flex items-center gap-1.5 px-2 py-1 bg-primary/10 text-primary border-primary/20">
              <FlaskConical className="h-3 w-3" /> A/B тест
            </Badge>
          )}
        </div>
      </div>

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

      {/* Причина паузы */}
      {isPausedDailyLimit && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950/20 dark:border-amber-800">
          <Clock className="h-5 w-5 text-amber-600" />
          <div>
            <p className="font-medium text-amber-800 dark:text-amber-200">Достигнут дневной лимит отправки</p>
            <p className="text-sm text-amber-600 dark:text-amber-400">
              Кампания приостановлена автоматически. Продолжите отправку завтра или измените EMAIL_DAILY_LIMIT.
            </p>
          </div>
        </div>
      )}

      {/* Прогресс */}
      <Card className="border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            {isRunning ? <Zap className="h-5 w-5 text-primary animate-pulse" /> : <Mail className="h-5 w-5" />}
            Ход рассылки
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Прогресс</span>
              <span className="font-bold text-foreground">{progress}%</span>
            </div>
            <Progress value={progress} className="h-3" />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Отправлено: {currentSent}</span>
              <span>Всего: {currentTotal}</span>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4 pt-4 border-t">
            <div className="text-center p-3 rounded-xl bg-muted">
              <p className="text-2xl font-bold">{currentSent}</p>
              <p className="text-[10px] uppercase font-semibold text-muted-foreground">Отправлено</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-success/10">
              <p className="text-2xl font-bold text-success">{campaign.total_opened}</p>
              <p className="text-[10px] uppercase font-semibold text-muted-foreground">Открыто</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-primary/10">
              <p className="text-2xl font-bold text-primary">{campaign.total_replied}</p>
              <p className="text-[10px] uppercase font-semibold text-muted-foreground">Ответов</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-destructive/10">
              <p className="text-2xl font-bold text-destructive">{currentErrors}</p>
              <p className="text-[10px] uppercase font-semibold text-muted-foreground">Ошибок</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-4 border-t">
            <div className="text-center p-3 rounded-xl bg-muted">
              <p className="text-xl font-bold text-success">{campaign.open_rate}%</p>
              <p className="text-[10px] uppercase font-semibold text-muted-foreground">Open Rate</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-muted">
              <p className="text-xl font-bold text-primary">
                {campaign.total_sent > 0 ? Math.round((campaign.total_replied / campaign.total_sent) * 100) : 0}%
              </p>
              <p className="text-[10px] uppercase font-semibold text-muted-foreground">Reply Rate</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* A/B Сравнение */}
      {hasAB && abStats && abStats.variants && Object.keys(abStats.variants).length > 0 && (
        <Card className="border-primary/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <FlaskConical className="h-5 w-5 text-primary" />
              A/B Сравнение
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(abStats.variants).map(([variant, variantData]) => (
                <div key={variant} className={cn(
                  "p-4 rounded-xl border-2",
                  variant === 'A' ? 'border-blue-300 bg-blue-50 dark:bg-blue-950/20' : 'border-purple-300 bg-purple-50 dark:bg-purple-950/20'
                )}>
                  <div className="flex items-center gap-2 mb-3">
                    <Badge variant="outline" className={cn(
                      "text-sm px-2",
                      variant === 'A' ? 'border-blue-400 text-blue-700' : 'border-purple-400 text-purple-700'
                    )}>
                      Вариант {variant}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mb-2 line-clamp-2">{variantData.subject}</p>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <p className="text-lg font-bold">{variantData.sent}</p>
                      <p className="text-[9px] uppercase text-muted-foreground">Отправлено</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-success">{variantData.opened}</p>
                      <p className="text-[9px] uppercase text-muted-foreground">Открыто</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-primary">{variantData.replied}</p>
                      <p className="text-[9px] uppercase text-muted-foreground">Ответов</p>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t text-center">
                    <p className="text-sm font-bold text-primary">{variantData.reply_rate}% Reply Rate</p>
                  </div>
                </div>
              ))}
            </div>
            {abStats.note && (
              <p className="mt-3 text-xs text-muted-foreground text-center">{abStats.note}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* P4R-M19: Ошибка загрузки A/B статистики */}
      {hasAB && abStatsError && !abStats && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/5 border border-destructive/20">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          <p className="text-sm text-destructive">{abStatsError}</p>
        </div>
      )}

      {/* Фильтры кампании */}
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
    </div>
  );
}
