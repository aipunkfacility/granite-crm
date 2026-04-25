'use client';

import { useCampaigns, useCampaignTemplates } from "@/lib/hooks/use-campaigns";
import { createCampaign, runCampaign, pauseCampaign, deleteCampaign } from "@/lib/api/campaigns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
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
  X,
  Send,
} from "lucide-react";
import { format } from "date-fns";
import { ru } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

const STATUS_CONFIG: Record<string, { label: string, variant: string, icon: any }> = {
  draft: { label: "Черновик", variant: "secondary", icon: Clock },
  running: { label: "Запущена", variant: "default", icon: Play },
  paused: { label: "Пауза", variant: "outline", icon: Pause },
  completed: { label: "Завершена", variant: "success" as any, icon: CheckCircle2 },
};

/* Create Campaign Dialog */
function CreateCampaignDialog({
  isOpen,
  onClose,
  onCreated,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { data: templates } = useCampaignTemplates();
  const [name, setName] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [filterCity, setFilterCity] = useState('');
  const [filterSegment, setFilterSegment] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!name.trim() || !templateName) return;
    setIsSaving(true);
    setError(null);
    try {
      const filters: Record<string, any> = {};
      if (filterCity) filters.city = filterCity;
      if (filterSegment) filters.segment = filterSegment;
      await createCampaign({
        name: name.trim(),
        template_name: templateName,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
      });
      setName('');
      setTemplateName('');
      setFilterCity('');
      setFilterSegment('');
      onCreated();
      onClose();
    } catch (e: any) {
      setError(e?.message || 'Ошибка создания');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetAndClose = () => {
    setName('');
    setTemplateName('');
    setFilterCity('');
    setFilterSegment('');
    setError(null);
    onClose();
  };

  const emailTemplates = (templates || []).filter(t => t.channel === 'email');

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-border">
        <div className="p-6 border-b bg-primary/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Send className="h-5 w-5 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">Новая кампания</h2>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleResetAndClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Название</label>
            <Input
              placeholder="Например: Холодные лиды МСК"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Шаблон письма</label>
            <select
              value={templateName}
              onChange={e => setTemplateName(e.target.value)}
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
            >
              <option value="">Выберите шаблон...</option>
              {emailTemplates.map(t => (
                <option key={t.name} value={t.name}>{t.name} {t.subject ? `— ${t.subject}` : ''}</option>
              ))}
            </select>
            {emailTemplates.length === 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                Нет email-шаблонов. Создайте шаблон через API.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Город (фильтр)</label>
              <Input
                placeholder="Необязательно"
                value={filterCity}
                onChange={e => setFilterCity(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Сегмент (фильтр)</label>
              <select
                value={filterSegment}
                onChange={e => setFilterSegment(e.target.value)}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              >
                <option value="">Все сегменты</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
              </select>
            </div>
          </div>
        </div>

        {error && (
          <div className="px-6 py-3 bg-destructive/5 border-t">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={handleResetAndClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button onClick={handleSubmit} disabled={!name.trim() || !templateName || isSaving}>
            {isSaving ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Создание...</>
            ) : (
              <><Plus className="mr-2 h-4 w-4" /> Создать</>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function CampaignsPage() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.items || [];
  const [createOpen, setCreateOpen] = useState(false);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [pausingId, setPausingId] = useState<number | null>(null);
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
            const progress = campaign.total_targets > 0 
              ? Math.round((campaign.sent_count / campaign.total_targets) * 100) 
              : 0;
            const openRate = campaign.sent_count > 0 
              ? Math.round((campaign.open_count / campaign.sent_count) * 100) 
              : 0;

            return (
              <Card key={campaign.id} className="overflow-hidden border-border hover:shadow-md transition-shadow">
                <CardHeader className="border-b bg-muted/50 py-4 px-6 flex flex-row items-center justify-between space-y-0">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-bold">{campaign.name}</CardTitle>
                    <p className="text-xs text-muted-foreground">Шаблон: <span className="font-mono text-primary">{campaign.template_name}</span></p>
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
                      <span>Отправлено: {campaign.sent_count}</span>
                      <span>Всего: {campaign.total_targets}</span>
                    </div>
                  </div>

                  {/* Статистика */}
                  <div className="grid grid-cols-3 gap-4 border-t pt-6">
                    <div className="text-center">
                      <div className="flex items-center justify-center text-muted-foreground mb-1">
                        <Users className="h-4 w-4" />
                      </div>
                      <p className="text-xl font-bold text-foreground">{campaign.sent_count}</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Охват</p>
                    </div>
                    <div className="text-center border-x">
                      <div className="flex items-center justify-center text-success mb-1">
                        <BarChart2 className="h-4 w-4" />
                      </div>
                      <p className="text-xl font-bold text-success">{openRate}%</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Open Rate</p>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center text-primary mb-1">
                        <CheckCircle2 className="h-4 w-4" />
                      </div>
                      <p className="text-xl font-bold text-primary">{campaign.replied_count}</p>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold">Ответов</p>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    {campaign.status === 'draft' || campaign.status === 'paused' ? (
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

      <CreateCampaignDialog
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ['campaigns'] })}
      />
    </div>
  );
}
