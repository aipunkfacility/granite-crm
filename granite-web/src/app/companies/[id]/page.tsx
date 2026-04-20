'use client';

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchCompany, updateCompany } from "@/lib/api/companies";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { 
  ArrowLeft, 
  Globe, 
  Mail, 
  MapPin, 
  Phone, 
  Send, 
  MessageSquare, 
  ShieldCheck,
  Building,
  CheckCircle2
} from "lucide-react";
import { FUNNEL_STAGES, SEGMENT_CONFIG } from "@/constants/funnel";
import { FunnelStage } from "@/lib/types/api";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { useDebouncedCallback } from "use-debounce";

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = parseInt(params.id as string);

  const { data: company, isLoading, error } = useQuery({
    queryKey: ['company', id],
    queryFn: () => fetchCompany(id),
  });

  const updateMutation = useMutation({
    mutationFn: (updates: any) => updateCompany(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company', id] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
    onError: (err: Error) => {
      toast.error(`Ошибка сохранения: ${err.message}`);
    }
  });

  // Локальное состояние для заметок (для мгновенного ввода)
  const [notes, setNotes] = useState("");
  
  useEffect(() => {
    if (company) setNotes(company.notes || "");
  }, [company]);

  // Автосохранение заметок через 1 секунду
  const debouncedSaveNotes = useDebouncedCallback((value: string) => {
    updateMutation.mutate({ notes: value });
    toast.success("Заметки сохранены");
  }, 1000);

  if (isLoading) return <div className="p-8">Загрузка...</div>;
  if (error || !company) return <div className="p-8 text-destructive">Ошибка: {(error as Error)?.message}</div>;

  const stage = FUNNEL_STAGES[company.funnel_stage];
  const segment = company.segment ? SEGMENT_CONFIG[company.segment] : null;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-20">
      <Button 
        variant="ghost" 
        onClick={() => router.back()} 
        className="mb-2 -ml-2 text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Назад к списку
      </Button>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Левая колонка: Инфо */}
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div className="space-y-1">
                <CardTitle className="text-2xl font-bold">{company.name}</CardTitle>
                <div className="flex items-center text-slate-500 text-sm">
                  <MapPin className="mr-1 h-3 w-3" />
                  {company.city}, {company.region}
                </div>
              </div>
              <div className="flex gap-2">
                {segment && (
                  <Badge variant={segment.variant} className="px-3 py-1 text-sm">
                    Сегмент {segment.label}
                  </Badge>
                )}
                <Badge variant="outline" className="px-3 py-1 text-sm font-mono">
                  Score: {company.crm_score}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Контакты</h3>
                  <div className="space-y-2">
                    {company.phones.map(p => (
                      <div key={p} className="flex items-center text-sm">
                        <Phone className="mr-2 h-4 w-4 text-slate-400" />
                        <a href={`tel:${p}`} className="hover:text-indigo-600">{p}</a>
                      </div>
                    ))}
                    {company.emails.map(e => (
                      <div key={e} className="flex items-center text-sm">
                        <Mail className="mr-2 h-4 w-4 text-slate-400" />
                        <a href={`mailto:${e}`} className="hover:text-indigo-600">{e}</a>
                      </div>
                    ))}
                    {company.website && (
                      <div className="flex items-center text-sm">
                        <Globe className="mr-2 h-4 w-4 text-slate-400" />
                        <a href={company.website} target="_blank" rel="noreferrer" className="hover:text-indigo-600 truncate">
                          {company.website}
                        </a>
                      </div>
                    )}
                  </div>
                </div>
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Мессенджеры</h3>
                  <div className="flex flex-wrap gap-2">
                    {company.telegram && (
                      <Button variant="outline" size="sm" asChild>
                        <a href={`https://t.me/${company.telegram.replace('@', '')}`} target="_blank" rel="noreferrer">
                          <Send className="mr-2 h-4 w-4 text-sky-500" /> Telegram
                        </a>
                      </Button>
                    )}
                    {company.whatsapp && (
                      <Button variant="outline" size="sm" asChild>
                        <a href={`https://wa.me/${company.whatsapp}`} target="_blank" rel="noreferrer">
                          <MessageSquare className="mr-2 h-4 w-4 text-emerald-500" /> WhatsApp
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t grid grid-cols-3 gap-4 text-xs">
                <div className="p-3 rounded-lg bg-slate-50 border">
                  <p className="text-slate-400 mb-1">CMS</p>
                  <p className="font-medium">{company.cms || 'Не определено'}</p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 border">
                  <p className="text-slate-400 mb-1">Сеть</p>
                  <p className="font-medium flex items-center">
                    {company.is_network ? <ShieldCheck className="mr-1 h-3 w-3 text-emerald-500" /> : <Building className="mr-1 h-3 w-3 text-slate-400" />}
                    {company.is_network ? 'Да' : 'Нет'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 border">
                  <p className="text-slate-400 mb-1">Квиз Marquiz</p>
                  <p className="font-medium">{company.has_marquiz ? 'Есть' : 'Нет'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Заметки</CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea 
                placeholder="Добавьте важную информацию о компании..."
                className="min-h-[200px] resize-none focus-visible:ring-indigo-500"
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value);
                  debouncedSaveNotes(e.target.value);
                }}
              />
              <p className="mt-2 text-xs text-slate-400 italic">
                {updateMutation.isPending ? "Сохранение..." : "Автосохранение включено"}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Правая колонка: CRM */}
        <div className="space-y-6">
          <Card className="border-indigo-100 bg-indigo-50/30">
            <CardHeader>
              <CardTitle className="text-lg">Воронка продаж</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-500 uppercase">Текущая стадия</p>
                <Badge variant={stage.variant} className="w-full justify-center py-2 text-sm uppercase tracking-wide">
                  {stage.label}
                </Badge>
              </div>

              <div className="pt-4 space-y-2">
                <p className="text-xs font-semibold text-slate-500 uppercase mb-3">Сменить стадию</p>
                <div className="grid grid-cols-1 gap-2">
                  {(Object.keys(FUNNEL_STAGES) as FunnelStage[]).map((s) => (
                    <Button 
                      key={s}
                      variant={company.funnel_stage === s ? "default" : "outline"}
                      size="sm"
                      className="justify-start font-normal"
                      onClick={() => {
                        updateMutation.mutate({ funnel_stage: s });
                        toast.success(`Статус изменен на: ${FUNNEL_STAGES[s].label}`);
                      }}
                    >
                      {company.funnel_stage === s && <CheckCircle2 className="mr-2 h-4 w-4" />}
                      {FUNNEL_STAGES[s].label}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-indigo-100 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-600">Остановить автоматизацию</span>
                <input 
                  type="checkbox" 
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  checked={company.stop_automation}
                  onChange={(e) => {
                    updateMutation.mutate({ stop_automation: e.target.checked });
                  }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Активность</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Email отправлено</span>
                <span className="font-semibold">{company.email_sent_count}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Email открыто</span>
                <span className="font-semibold text-emerald-600">{company.email_opened_count}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">TG / WA касаний</span>
                <span className="font-semibold">{company.tg_sent_count + company.wa_sent_count}</span>
              </div>
              <div className="pt-4 border-t text-xs text-slate-400">
                ID компании: <span className="font-mono">{company.id}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
