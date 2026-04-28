'use client';

import { useCampaigns, useCampaignTemplates } from "@/lib/hooks/use-campaigns";
import { runCampaign, pauseCampaign, deleteCampaign, fetchCampaignDetail, fetchABStats } from "@/lib/api/campaigns";
import { CampaignWizard } from "@/components/campaigns/CampaignWizard";
import { CampaignDashboard } from "@/components/campaigns/CampaignDashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { 
  Mail, 
  Play, 
  Pause, 
  CheckCircle2, 
  Clock, 
  Users,
  BarChart2,
  Plus,
  Trash2,
  Loader2,
  Send,
  AlertTriangle,
  Eye,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

const STATUS_CONFIG: Record<string, { label: string, variant: string, icon: any }> = {
  draft: { label: "Черновик", variant: "secondary", icon: Clock },
  running: { label: "Запущена", variant: "default", icon: Play },
  paused: { label: "Пауза", variant: "outline", icon: Pause },
  paused_daily_limit: { label: "Лимит", variant: "outline", icon: Pause },
  completed: { label: "Завершена", variant: "success" as any, icon: CheckCircle2 },
};

export default function CampaignsPage() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.items || [];
  const [createOpen, setCreateOpen] = useState(false);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [pausingId, setPausingId] = useState<number | null>(null);
  const [dashboardId, setDashboardId] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const handleRun = async (id: number) => {
    setRunningId(id);
    try {
      await runCampaign(id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e: any) {
      alert(e?.message || 'Ошибка запуска');
    } finally {
      setRunningId(null);
    }
  };

  const handlePause = async (id: number) => {
    setPausingId(id);
    try {
      await pauseCampaign(id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e: any) {
      alert(e?.message || 'Ошибка паузы');
    } finally {
      setPausingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить черновик кампании?')) return;
    try {
      await deleteCampaign(id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e: any) {
      alert(e?.message || 'Ошибка удаления');
    }
  };

  // Если открыт дашборд — показываем его
  if (dashboardId !== null) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => setDashboardId(null)}>
          ← Назад к списку кампаний
        </Button>
        <CampaignDashboard 
          campaignId={dashboardId} 
          onClose={() => setDashboardId(null)} 
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Кампании</h1>
          <p className="text-muted-foreground">Управление массовыми email-рассылками и отслеживание прогресса.</p>
        </div>
        <Button className="bg-primary hover:bg-primary" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> Создать кампанию
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2].map(i => <div key={i} className="h-64 w-full bg-muted animate-pulse rounded-xl" />)}
        </div>
      ) : campaigns.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed rounded-xl bg-muted/50">
          <Mail className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-medium text-foreground">Нет активных кампаний</h3>
          <p className="text-muted-foreground mt-1">Создайте свою первую рассылку, чтобы начать привлекать клиентов.</p>
          <Button className="mt-4" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Создать кампанию
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {campaigns.map((campaign) => {
            const status = STATUS_CONFIG[campaign.status] || STATUS_CONFIG.draft;
            const totalTargets = campaign.total_recipients || campaign.total_sent || 0;
            const progress = totalTargets > 0 
              ? Math.round((campaign.total_sent / totalTargets) * 100) 
              : 0;
            const openRate = campaign.total_sent > 0 
              ? Math.round((campaign.total_opened / campaign.total_sent) * 100) 
              : 0;
            const hasAB = !!(campaign.subject_a && campaign.subject_b);

            return (
              <Card key={campaign.id} className="overflow-hidden border-border hover:shadow-md transition-shadow">
                <CardHeader className="border-b bg-muted/50 py-4 px-6 flex flex-row items-center justify-between space-y-0">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-bold cursor-pointer hover:text-primary" onClick={() => setDashboardId(campaign.id)}>
                      {campaign.name}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <p className="text-xs text-muted-foreground">Шаблон: <span className="font-mono text-primary">{campaign.template_name}</span></p>
                      {hasAB && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-primary/10 text-primary border-primary/20">
                          A/B тест
                        </Badge>
                      )}
                    </div>
                  </div>
                  <Badge variant={status.variant as any} className="flex items-center gap-1.5 px-3 py-1">
                    <status.icon className={cn("h-3 w-3", campaign.status === 'running' && "animate-pulse")} />
                    {status.label}
                  </Badge>
                </CardHeader>
                <CardContent className="p-6 space-y-6">
                  {/* Прогресс отправки */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground font-medium">Прогресс рассылки</span>
                      <span className="font-bold text-foreground">{progress}%</span>
                    </div>
                    <Progress value={progress} className="h-2" />
                    <div className="flex justify-between text-[11px] text-muted-foreground">
                      <span>Отправлено: {campaign.total_sent}</span>
                      <span>Всего: {totalTargets}</span>
                    </div>
                  </div>

                  {/* Статистика */}
                  <div className="grid grid-cols-4 gap-3 border-t pt-6">
                    <div className="text-center">
                      <p className="text-xl font-bold text-foreground">{campaign.total_sent}</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Охват</p>
                    </div>
                    <div className="text-center border-x">
                      <p className="text-xl font-bold text-success">{openRate}%</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Open Rate</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xl font-bold text-primary">{campaign.total_replied}</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Ответов</p>
                    </div>
                    <div className="text-center border-l">
                      <p className="text-xl font-bold text-destructive">{campaign.total_errors || 0}</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Ошибок</p>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => setDashboardId(campaign.id)}
                    >
                      <Eye className="mr-1 h-3 w-3" /> Дашборд
                    </Button>
                    {campaign.status === 'draft' || campaign.status === 'paused' || campaign.status === 'paused_daily_limit' ? (
                      <Button
                        className="flex-1 bg-success hover:bg-success/90 text-success-foreground h-9"
                        onClick={() => handleRun(campaign.id)}
                        disabled={runningId === campaign.id}
                      >
                        {runningId === campaign.id ? (
                          <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Запуск...</>
                        ) : (
                          <><Play className="mr-2 h-4 w-4 fill-current" /> Запустить</>
                        )}
                      </Button>
                    ) : campaign.status === 'running' ? (
                      <Button
                        variant="outline"
                        className="flex-1 h-9"
                        onClick={() => handlePause(campaign.id)}
                        disabled={pausingId === campaign.id}
                      >
                        {pausingId === campaign.id ? (
                          <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Приостановка...</>
                        ) : (
                          <><Pause className="mr-2 h-4 w-4" /> Пауза</>
                        )}
                      </Button>
                    ) : null}
                    {campaign.status === 'draft' && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 text-muted-foreground hover:text-destructive"
                        onClick={() => handleDelete(campaign.id)}
                        title="Удалить черновик"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <CampaignWizard
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ['campaigns'] })}
      />
    </div>
  );
}
