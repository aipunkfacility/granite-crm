'use client';

import { useCampaigns } from "@/lib/hooks/use-campaigns";
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
  Plus
} from "lucide-react";
import { format } from "date-fns";
import { ru } from "date-fns/locale";
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<string, { label: string, variant: string, icon: any }> = {
  draft: { label: "Черновик", variant: "secondary", icon: Clock },
  running: { label: "Запущена", variant: "default", icon: Play },
  paused: { label: "Пауза", variant: "outline", icon: Pause },
  completed: { label: "Завершена", variant: "success" as any, icon: CheckCircle2 },
};

export default function CampaignsPage() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Кампании</h1>
          <p className="text-slate-500">Управление массовыми рассылками и отслеживание прогресса.</p>
        </div>
        <Button className="bg-indigo-600 hover:bg-indigo-700">
          <Plus className="mr-2 h-4 w-4" /> Создать кампанию
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2].map(i => <div key={i} className="h-64 w-full bg-slate-100 animate-pulse rounded-xl" />)}
        </div>
      ) : campaigns.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed rounded-xl bg-slate-50/50">
          <Mail className="mx-auto h-12 w-12 text-slate-300" />
          <h3 className="mt-4 text-lg font-medium text-slate-900">Нет активных кампаний</h3>
          <p className="text-slate-500 mt-1">Создайте свою первую рассылку, чтобы начать привлекать клиентов.</p>
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
              <Card key={campaign.id} className="overflow-hidden border-slate-200 hover:shadow-md transition-shadow">
                <CardHeader className="border-b bg-slate-50/50 py-4 px-6 flex flex-row items-center justify-between space-y-0">
                  <div className="space-y-1">
                    <CardTitle className="text-lg font-bold">{campaign.name}</CardTitle>
                    <p className="text-xs text-slate-500">Шаблон: <span className="font-mono text-indigo-600">{campaign.template_name}</span></p>
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
                      <span className="text-slate-500 font-medium">Прогресс рассылки</span>
                      <span className="font-bold text-slate-900">{progress}%</span>
                    </div>
                    <Progress value={progress} className="h-2" />
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Отправлено: {campaign.sent_count}</span>
                      <span>Всего: {campaign.total_targets}</span>
                    </div>
                  </div>

                  {/* Статистика */}
                  <div className="grid grid-cols-3 gap-4 border-t pt-6">
                    <div className="text-center">
                      <div className="flex items-center justify-center text-slate-400 mb-1">
                        <Users className="h-4 w-4" />
                      </div>
                      <p className="text-xl font-bold text-slate-900">{campaign.sent_count}</p>
                      <p className="text-[10px] text-slate-500 uppercase font-semibold">Охват</p>
                    </div>
                    <div className="text-center border-x">
                      <div className="flex items-center justify-center text-emerald-500 mb-1">
                        <BarChart2 className="h-4 w-4" />
                      </div>
                      <p className="text-xl font-bold text-emerald-600">{openRate}%</p>
                      <p className="text-[10px] text-slate-500 uppercase font-semibold">Open Rate</p>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center text-indigo-500 mb-1">
                        <CheckCircle2 className="h-4 w-4" />
                      </div>
                      <p className="text-xl font-bold text-indigo-600">{campaign.replied_count}</p>
                      <p className="text-[10px] text-slate-500 uppercase font-semibold">Ответов</p>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    {campaign.status === 'draft' || campaign.status === 'paused' ? (
                      <Button className="flex-1 bg-emerald-600 hover:bg-emerald-700 h-9">
                        <Play className="mr-2 h-4 w-4 fill-current" /> Запустить
                      </Button>
                    ) : (
                      <Button variant="outline" className="flex-1 h-9">
                        <Pause className="mr-2 h-4 w-4" /> Пауза
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" className="h-9 w-9 text-slate-400">
                      <BarChart2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
