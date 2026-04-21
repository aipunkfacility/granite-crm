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
  CheckCircle2,
  Edit2,
  RefreshCcw,
  Plus
} from "lucide-react";
import { FUNNEL_STAGES, SEGMENT_CONFIG } from "@/constants/funnel";
import { FunnelStage } from "@/lib/types/api";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { useDebouncedCallback } from "use-debounce";
import { CompanyEditDialog } from "@/components/companies/CompanyEditDialog";
import { ReEnrichDialog } from "@/components/companies/ReEnrichDialog";

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = parseInt(params.id as string);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isReEnrichOpen, setIsReEnrichOpen] = useState(false);

  const { data: company, isLoading, error } = useQuery({
    queryKey: ['company', id],
    queryFn: () => fetchCompany(id),
  });

  const updateMutation = useMutation({
    mutationFn: (updates: any) => updateCompany(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company', id] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success("Компания обновлена");
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
  }, 1000);

  if (isLoading) return <div className="p-8">Загрузка...</div>;
  if (error || !company) return <div className="p-8 text-destructive">Ошибка: {(error as Error)?.message}</div>;

  const stage = FUNNEL_STAGES[company.funnel_stage];
  const segment = company.segment ? SEGMENT_CONFIG[company.segment] : null;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-20 p-4 md:p-0">
      <div className="flex items-center justify-between">
        <Button 
          variant="ghost" 
          onClick={() => router.back()} 
          className="-ml-2 text-slate-500 hover:text-slate-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Назад к списку
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Левая колонка: Инфо */}
        <div className="md:col-span-2 space-y-6">
          <Card className="overflow-hidden border-slate-200">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 bg-slate-50/50 border-b pb-4">
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <CardTitle className="text-2xl font-bold">{company.name}</CardTitle>
                  <Button 
                    variant="outline" 
                    size="icon" 
                    className="h-8 w-8 rounded-full" 
                    onClick={() => setIsEditOpen(true)}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                </div>
                <div className="flex items-center text-slate-500 text-sm">
                  <MapPin className="mr-1 h-3 w-3" />
                  {company.city}, {company.region}
                </div>
              </div>
              <div className="flex gap-2">
                {segment && (
                  <Badge variant={segment.variant} className="px-3 py-1 text-sm bg-white shadow-sm">
                    Сегмент {segment.label}
                  </Badge>
                )}
                <Badge variant="outline" className="px-3 py-1 text-sm font-mono bg-white shadow-sm">
                  Score: {company.crm_score}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 pt-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Контакты</h3>
                  <div className="space-y-2">
                    {company.phones.map(p => (
                      <div key={p} className="flex items-center text-sm group">
                        <Phone className="mr-2 h-4 w-4 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                        <a href={`tel:${p}`} className="hover:text-indigo-600 font-medium">{p}</a>
                      </div>
                    ))}
                    {company.emails.map(e => (
                      <div key={e} className="flex items-center text-sm group">
                        <Mail className="mr-2 h-4 w-4 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                        <a href={`mailto:${e}`} className="hover:text-indigo-600 font-medium">{e}</a>
                      </div>
                    ))}
                    {company.website && (
                      <div className="flex items-center text-sm group">
                        <Globe className="mr-2 h-4 w-4 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                        <a href={company.website} target="_blank" rel="noreferrer" className="hover:text-indigo-600 font-medium truncate">
                          {company.website}
                        </a>
                      </div>
                    )}
                  </div>
                </div>
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Мессенджеры</h3>
                  <div className="flex flex-wrap gap-2">
                    {company.telegram && (
                      <Button variant="outline" size="sm" asChild className="border-sky-100 hover:bg-sky-50">
                        <a href={company.telegram.startsWith('http') ? company.telegram : `https://t.me/${company.telegram.replace('@', '')}`} target="_blank" rel="noreferrer">
                          <Send className="mr-2 h-4 w-4 text-sky-500" /> Telegram
                        </a>
                      </Button>
                    )}
                    {company.whatsapp && (
                      <Button variant="outline" size="sm" asChild className="border-emerald-100 hover:bg-emerald-50">
                        <a href={company.whatsapp.startsWith('http') ? company.whatsapp : `https://wa.me/${company.whatsapp}`} target="_blank" rel="noreferrer">
                          <MessageSquare className="mr-2 h-4 w-4 text-emerald-500" /> WhatsApp
                        </a>
                      </Button>
                    )}
                    {(!company.telegram && !company.whatsapp) && (
                      <p className="text-sm text-slate-400 italic">Не указаны</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t grid grid-cols-3 gap-4 text-xs">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <p className="text-slate-400 mb-1 font-semibold uppercase text-[10px] tracking-wider">CMS</p>
                  <p className="font-bold text-slate-700">{company.cms || 'НЕ ОПРЕДЕЛЕНО'}</p>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <p className="text-slate-400 mb-1 font-semibold uppercase text-[10px] tracking-wider">СЕТЬ</p>
                  <p className="font-bold text-slate-700 flex items-center">
                    {company.is_network ? <ShieldCheck className="mr-1 h-3 w-3 text-emerald-500" /> : <Building className="mr-1 h-3 w-3 text-slate-400" />}
                    {company.is_network ? 'ДА' : 'НЕТ'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <p className="text-slate-400 mb-1 font-semibold uppercase text-[10px] tracking-wider">КВИЗ MARQUIZ</p>
                  <p className="font-bold text-slate-700">{company.has_marquiz ? 'ЕСТЬ' : 'НЕТ'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200">
            <CardHeader className="border-b pb-4 flex flex-row items-center justify-between">
              <CardTitle className="text-lg">Заметки</CardTitle>
              <div className="text-[10px] uppercase font-bold text-slate-400">
                {updateMutation.isPending ? "Сохранение..." : "Автосохранение"}
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <Textarea 
                placeholder="Добавьте важную информацию о компании..."
                className="min-h-[220px] resize-none border-none p-0 focus-visible:ring-0 text-slate-700 leading-relaxed"
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value);
                  debouncedSaveNotes(e.target.value);
                }}
              />
            </CardContent>
          </Card>
        </div>

        {/* Правая колонка: CRM */}
        <div className="space-y-6">
          <Card className="border-indigo-200 bg-indigo-50/20 shadow-sm shadow-indigo-100/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center text-indigo-900">
                <CheckCircle2 className="mr-2 h-5 w-5 text-indigo-500" />
                Воронка продаж
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest">Текущая стадия</p>
                <Badge variant={stage.variant} className="w-full justify-center py-2.5 text-xs font-bold uppercase tracking-widest bg-white shadow-sm">
                  {stage.label}
                </Badge>
              </div>

              <div className="pt-4 space-y-2">
                <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest mb-3">Сменить стадию</p>
                <div className="grid grid-cols-1 gap-1.5">
                  {(Object.keys(FUNNEL_STAGES) as FunnelStage[]).map((s) => (
                    <Button 
                      key={s}
                      variant={company.funnel_stage === s ? "default" : "outline"}
                      size="sm"
                      className={`justify-start font-medium text-xs h-9 ${company.funnel_stage === s ? 'bg-indigo-600 shadow-md' : 'bg-white border-indigo-100 text-indigo-700 hover:bg-indigo-50'}`}
                      onClick={() => {
                        updateMutation.mutate({ funnel_stage: s });
                      }}
                    >
                      {company.funnel_stage === s && <CheckCircle2 className="mr-2 h-3 w-3" />}
                      {FUNNEL_STAGES[s].label}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="pt-6 mt-4 border-t border-indigo-100 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-indigo-900">Стоп-автоматизация</span>
                  <input 
                    type="checkbox" 
                    className="h-4 w-4 rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
                    checked={company.stop_automation}
                    onChange={(e) => {
                      updateMutation.mutate({ stop_automation: e.target.checked });
                    }}
                  />
                </div>
                
                <Button 
                  variant="outline" 
                  className="w-full justify-start text-xs font-bold text-indigo-700 border-indigo-200 bg-white hover:bg-indigo-50"
                  onClick={() => setIsReEnrichOpen(true)}
                  disabled={!company.website}
                >
                  <RefreshCcw className="mr-2 h-3.5 w-3.5" />
                  Пересканировать сайт
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-lg">Активность</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4 text-sm font-medium text-slate-600">
              <div className="flex justify-between items-center p-2 rounded-lg bg-slate-50 border border-slate-100">
                <div className="flex items-center">
                  <Mail className="h-3.5 w-3.5 mr-2 text-slate-400" />
                  Email отправлено
                </div>
                <span className="text-indigo-600 font-bold">{company.email_sent_count}</span>
              </div>
              <div className="flex justify-between items-center p-2 rounded-lg bg-emerald-50/50 border border-emerald-100">
                <div className="flex items-center">
                  <CheckCircle2 className="h-3.5 w-3.5 mr-2 text-emerald-400" />
                  Email открыто
                </div>
                <span className="text-emerald-700 font-bold">{company.email_opened_count}</span>
              </div>
              <div className="flex justify-between items-center p-2 rounded-lg bg-sky-50/50 border border-sky-100">
                <div className="flex items-center">
                  <MessageSquare className="h-3.5 w-3.5 mr-2 text-sky-400" />
                  Мессенджеры
                </div>
                <span className="text-sky-700 font-bold">{company.tg_sent_count + company.wa_sent_count}</span>
              </div>
              <div className="pt-4 text-[10px] text-slate-400 uppercase tracking-widest flex justify-between">
                <span>ID компании</span>
                <span className="font-mono">{company.id}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <CompanyEditDialog 
        company={company} 
        isOpen={isEditOpen} 
        onClose={() => setIsEditOpen(false)} 
        onSave={(updates) => updateMutation.mutate(updates)}
        isSaving={updateMutation.isPending}
      />

      <ReEnrichDialog 
        companyId={company.id}
        isOpen={isReEnrichOpen}
        onClose={() => setIsReEnrichOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['company', id] })}
      />
    </div>
  );
}
