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
      {/* Sticky-панель: Назад + Пересканировать */}
      <div className="sticky top-0 z-30 -mx-4 -mt-4 mb-6 border-b bg-card/95 backdrop-blur px-4 py-3 flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Назад к списку
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsReEnrichOpen(true)}
          disabled={!company.website}
        >
          <RefreshCcw className="mr-2 h-3.5 w-3.5" />
          Пересканировать сайт
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Левая колонка: Инфо */}
        <div className="md:col-span-2 space-y-6">
          <Card className="overflow-hidden border-border">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 bg-muted/50 border-b pb-4">
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
                <div className="flex items-center text-muted-foreground text-sm">
                  <MapPin className="mr-1 h-3 w-3" />
                  {company.city}, {company.region}
                </div>
              </div>
              <div className="flex gap-2">
                {segment && (
                  <Badge variant={segment.variant} className="px-3 py-1 shadow-sm">
                    Сегмент {segment.label}
                  </Badge>
                )}
                <Badge variant="outline" className="px-3 py-1 text-sm font-mono bg-card shadow-sm">
                  Score: {company.crm_score}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 pt-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Контакты</h3>
                  <div className="space-y-2">
                    {company.phones.map(p => (
                      <div key={p} className="flex items-center text-sm group">
                        <Phone className="mr-2 h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                        <a href={`tel:${p}`} className="hover:text-primary font-medium">{p}</a>
                      </div>
                    ))}
                    {company.emails.map(e => (
                      <div key={e} className="flex items-center text-sm group">
                        <Mail className="mr-2 h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                        <a href={`mailto:${e}`} className="hover:text-primary font-medium">{e}</a>
                      </div>
                    ))}
                    {company.website && (
                      <div className="flex items-center text-sm group">
                        <Globe className="mr-2 h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                        <a href={company.website} target="_blank" rel="noreferrer" className="hover:text-primary font-medium truncate">
                          {company.website}
                        </a>
                      </div>
                    )}
                  </div>
                </div>
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Мессенджеры</h3>
                  <div className="flex flex-wrap gap-2">
                    {company.telegram && (
                      <Button variant="outline" size="sm" asChild className="border-info/20 hover:bg-info/10">
                        <a href={company.telegram.startsWith('http') ? company.telegram : `https://t.me/${company.telegram.replace('@', '')}`} target="_blank" rel="noreferrer">
                          <Send className="mr-2 h-4 w-4 text-info" /> Telegram
                        </a>
                      </Button>
                    )}
                    {company.whatsapp && (
                      <Button variant="outline" size="sm" asChild className="border-success/20 hover:bg-success/10">
                        <a href={company.whatsapp.startsWith('http') ? company.whatsapp : `https://wa.me/${company.whatsapp}`} target="_blank" rel="noreferrer">
                          <MessageSquare className="mr-2 h-4 w-4 text-success" /> WhatsApp
                        </a>
                      </Button>
                    )}
                    {(!company.telegram && !company.whatsapp) && (
                      <p className="text-sm text-muted-foreground italic">Не указаны</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t grid grid-cols-3 gap-4 text-xs">
                <div className="p-3 rounded-xl bg-muted border border-border">
                  <p className="text-muted-foreground mb-1 font-semibold uppercase text-[10px] tracking-wider">CMS</p>
                  <p className="font-bold text-foreground">{company.cms || 'НЕ ОПРЕДЕЛЕНО'}</p>
                </div>
                <div className="p-3 rounded-xl bg-muted border border-border">
                  <p className="text-muted-foreground mb-1 font-semibold uppercase text-[10px] tracking-wider">СЕТЬ</p>
                  <p className="font-bold text-foreground flex items-center">
                    {company.is_network ? <ShieldCheck className="mr-1 h-3 w-3 text-success" /> : <Building className="mr-1 h-3 w-3 text-muted-foreground" />}
                    {company.is_network ? 'ДА' : 'НЕТ'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-muted border border-border">
                  <p className="text-muted-foreground mb-1 font-semibold uppercase text-[10px] tracking-wider">КВИЗ MARQUIZ</p>
                  <p className="font-bold text-foreground">{company.has_marquiz ? 'ЕСТЬ' : 'НЕТ'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border">
            <CardHeader className="border-b pb-4 flex flex-row items-center justify-between">
              <CardTitle className="text-lg">Заметки</CardTitle>
              <div className="text-[10px] uppercase font-bold text-muted-foreground">
                {updateMutation.isPending ? "Сохранение..." : "Автосохранение"}
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <Textarea 
                placeholder="Добавьте важную информацию о компании..."
                className="min-h-[220px] resize-none border-none p-0 focus-visible:ring-0 text-foreground leading-relaxed"
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
          <Card className="border-primary/20 bg-primary/10 shadow-sm shadow-primary/10">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center text-primary">
                <CheckCircle2 className="mr-2 h-5 w-5 text-primary" />
                Воронка продаж
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <p className="text-[10px] font-bold text-primary/60 uppercase tracking-widest">Текущая стадия</p>
                <Badge variant={stage.variant} className="w-full justify-center py-2.5 text-xs font-bold uppercase tracking-widest bg-card shadow-sm">
                  {stage.label}
                </Badge>
              </div>

              <div className="pt-4 space-y-2">
                <p className="text-[10px] font-bold text-primary/60 uppercase tracking-widest mb-3">Сменить стадию</p>
                <div className="grid grid-cols-1 gap-1.5">
                  {(Object.keys(FUNNEL_STAGES) as FunnelStage[]).map((s) => (
                    <Button 
                      key={s}
                      variant={company.funnel_stage === s ? "default" : "outline"}
                      size="sm"
                      className={`justify-start font-medium text-xs h-9 ${company.funnel_stage === s ? 'bg-primary shadow-md' : 'bg-card border-primary/20 text-primary hover:bg-primary/10'}`}
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

              <div className="pt-6 mt-4 border-t border-primary/20 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-primary">Стоп-автоматизация</span>
                  <input 
                    type="checkbox" 
                    className="h-4 w-4 rounded border-primary/30 text-primary focus:ring-primary"
                    checked={company.stop_automation}
                    onChange={(e) => {
                      updateMutation.mutate({ stop_automation: e.target.checked });
                    }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border">
            <CardHeader className="pb-3 border-b">
              <CardTitle className="text-lg">Активность</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4 text-sm font-medium text-muted-foreground">
              <div className="flex justify-between items-center p-2 rounded-lg bg-muted border border-border">
                <div className="flex items-center">
                  <Mail className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
                  Email отправлено
                </div>
                <span className="text-primary font-bold">{company.email_sent_count}</span>
              </div>
              <div className="flex justify-between items-center p-2 rounded-lg bg-success/10 border border-success/20">
                <div className="flex items-center">
                  <CheckCircle2 className="h-3.5 w-3.5 mr-2 text-success/80" />
                  Email открыто
                </div>
                <span className="text-success font-bold">{company.email_opened_count}</span>
              </div>
              <div className="flex justify-between items-center p-2 rounded-lg bg-info/10 border border-info/20">
                <div className="flex items-center">
                  <MessageSquare className="h-3.5 w-3.5 mr-2 text-info/80" />
                  Мессенджеры
                </div>
                <span className="text-info font-bold">{company.tg_sent_count + company.wa_sent_count}</span>
              </div>
              <div className="pt-4 text-[10px] text-muted-foreground uppercase tracking-widest flex justify-between">
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
