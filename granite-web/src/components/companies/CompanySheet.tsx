'use client';

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchCompany, updateCompany } from "@/lib/api/companies";
import * as Dialog from "@radix-ui/react-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
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
  X,
} from "lucide-react";
import { FUNNEL_STAGES, SEGMENT_CONFIG } from "@/constants/funnel";
import { FunnelStage } from "@/lib/types/api";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { useDebouncedCallback } from "use-debounce";
import { CompanyEditDialog } from "@/components/companies/CompanyEditDialog";
import { ReEnrichDialog } from "@/components/companies/ReEnrichDialog";

/* V-01: Карточка компании — Sheet (side panel) вместо отдельной страницы */

interface CompanySheetProps {
  companyId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CompanySheet({ companyId, open, onOpenChange }: CompanySheetProps) {
  const queryClient = useQueryClient();

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isReEnrichOpen, setIsReEnrichOpen] = useState(false);

  const { data: company, isLoading, error } = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => fetchCompany(companyId!),
    enabled: open && !!companyId,
  });

  const updateMutation = useMutation({
    mutationFn: (updates: any) => updateCompany(companyId!, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success("Компания обновлена");
    },
    onError: (err: Error) => {
      toast.error(`Ошибка сохранения: ${err.message}`);
    }
  });

  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (company) setNotes(company.notes || "");
  }, [company]);

  const debouncedSaveNotes = useDebouncedCallback((value: string) => {
    updateMutation.mutate({ notes: value });
  }, 1000);

  if (!companyId) return null;

  const stage = company ? FUNNEL_STAGES[company.funnel_stage] : null;
  const segment = company?.segment ? SEGMENT_CONFIG[company.segment] : null;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed inset-y-0 right-0 z-50 w-full max-w-xl border-l bg-white shadow-2xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right duration-300 flex flex-col focus:outline-none"
        >
          {/* Header */}
          {isLoading ? (
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div className="h-6 w-48 animate-pulse rounded bg-slate-200" />
              <Dialog.Close asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8"><X className="h-4 w-4" /></Button>
              </Dialog.Close>
            </div>
          ) : error || !company ? (
            <div className="flex items-center justify-between border-b px-6 py-4">
              <span className="text-destructive text-sm">Ошибка загрузки</span>
              <Dialog.Close asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8"><X className="h-4 w-4" /></Button>
              </Dialog.Close>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b px-6 py-4 bg-slate-50/50">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="min-w-0">
                    {/* V-05: CardTitle font-semibold, not font-bold */}
                    <Dialog.Title className="text-lg font-semibold text-slate-900 truncate">
                      {company.name}
                    </Dialog.Title>
                    <div className="flex items-center text-sm text-slate-500 mt-0.5">
                      <MapPin className="mr-1 h-3 w-3 shrink-0" />
                      <span className="truncate">{company.city}, {company.region}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0 ml-3">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 rounded-full"
                    onClick={() => setIsReEnrichOpen(true)}
                    disabled={!company.website}
                  >
                    <RefreshCcw className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 rounded-full"
                    onClick={() => setIsEditOpen(true)}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                  <Dialog.Close asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <X className="h-4 w-4" />
                    </Button>
                  </Dialog.Close>
                </div>
              </div>

              {/* Scrollable body */}
              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                {/* Segment & Score */}
                <div className="flex gap-2 flex-wrap">
                  {segment && (
                    <Badge variant={segment.variant} className="px-3 py-1 shadow-sm">
                      Сегмент {segment.label}
                    </Badge>
                  )}
                  <Badge variant="outline" className="px-3 py-1 font-mono-code bg-white shadow-sm">
                    Score: {company.crm_score}
                  </Badge>
                </div>

                {/* Contacts + Messengers */}
                <div className="grid grid-cols-1 gap-5">
                  <div className="space-y-3">
                    {/* V-07, V-08: labels text-slate-500 font-medium */}
                    <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">Контакты</h3>
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
                    <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">Мессенджеры</h3>
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

                {/* CMS / Сеть / Quiz tiles */}
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                    {/* V-06: text-[10px] → text-xs, V-07: text-slate-400→500, V-08: font-semibold→font-medium */}
                    <p className="text-slate-500 mb-1 font-medium uppercase tracking-wider">CMS</p>
                    <p className="font-medium text-slate-700">{company.cms || 'НЕ ОПРЕДЕЛЕНО'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                    <p className="text-slate-500 mb-1 font-medium uppercase tracking-wider">СЕТЬ</p>
                    <p className="font-medium text-slate-700 flex items-center">
                      {company.is_network ? <ShieldCheck className="mr-1 h-3 w-3 text-emerald-500" /> : <Building className="mr-1 h-3 w-3 text-slate-400" />}
                      {company.is_network ? 'ДА' : 'НЕТ'}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                    <p className="text-slate-500 mb-1 font-medium uppercase tracking-wider">КВИЗ MARQUIZ</p>
                    <p className="font-medium text-slate-700">{company.has_marquiz ? 'ЕСТЬ' : 'НЕТ'}</p>
                  </div>
                </div>

                {/* Notes */}
                <Card className="border-slate-200">
                  <CardHeader className="border-b pb-3 flex flex-row items-center justify-between">
                    {/* V-20: CardTitle font-semibold */}
                    <CardTitle className="text-sm font-semibold">Заметки</CardTitle>
                    <div className="text-xs font-medium text-slate-500">
                      {updateMutation.isPending ? "Сохранение..." : "Автосохранение"}
                    </div>
                  </CardHeader>
                  <CardContent className="pt-4">
                    <Textarea
                      placeholder="Добавьте важную информацию о компании..."
                      className="min-h-[160px] resize-none border-none p-0 focus-visible:ring-0 text-slate-700 leading-relaxed"
                      value={notes}
                      onChange={(e) => {
                        setNotes(e.target.value);
                        debouncedSaveNotes(e.target.value);
                      }}
                    />
                  </CardContent>
                </Card>

                {/* Funnel */}
                <Card className="border-indigo-200 bg-indigo-50/20 shadow-sm shadow-indigo-100/50">
                  <CardHeader className="pb-3">
                    {/* V-20: CardTitle font-semibold */}
                    <CardTitle className="text-sm font-semibold flex items-center text-indigo-900">
                      <CheckCircle2 className="mr-2 h-4 w-4 text-indigo-500" />
                      Воронка продаж
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      {/* V-06,V-07,V-08: indigo context labels — keep indigo-400 but use text-xs font-medium */}
                      <p className="text-xs font-medium text-indigo-400 uppercase tracking-widest">Текущая стадия</p>
                      <Badge variant={stage!.variant} className="w-full justify-center py-2.5 text-xs font-bold uppercase tracking-widest bg-white shadow-sm">
                        {stage!.label}
                      </Badge>
                    </div>

                    <div className="pt-3 space-y-2">
                      <p className="text-xs font-medium text-indigo-400 uppercase tracking-widest mb-2">Сменить стадию</p>
                      <div className="grid grid-cols-1 gap-1.5">
                        {(Object.keys(FUNNEL_STAGES) as FunnelStage[]).map((s) => (
                          <Button
                            key={s}
                            variant={company.funnel_stage === s ? "default" : "outline"}
                            size="sm"
                            /* V-04: убран хардкод bg-indigo-600 — теперь variant="default" даёт indigo через --primary */
                            className={`justify-start font-medium text-xs h-9 ${company.funnel_stage === s ? '' : 'bg-white border-indigo-100 text-indigo-700 hover:bg-indigo-50'}`}
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

                    <div className="pt-4 mt-3 border-t border-indigo-100 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-indigo-900">Стоп-автоматизация</span>
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
                          checked={company.stop_automation}
                          onChange={(e) => {
                            updateMutation.mutate({ stop_automation: e.target.checked });
                          }}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Activity */}
                <Card className="border-slate-200">
                  <CardHeader className="pb-3 border-b">
                    {/* V-20: CardTitle font-semibold */}
                    <CardTitle className="text-sm font-semibold">Активность</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 pt-3 text-sm font-medium text-slate-600">
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
                    {/* V-06,V-07: text-[10px] → text-xs, text-slate-400 → text-slate-500 */}
                    <div className="pt-3 text-xs text-slate-500 uppercase tracking-widest flex justify-between">
                      <span>ID компании</span>
                      {/* V-10: font-mono-code (13px JetBrains Mono) */}
                      <span className="font-mono-code">{company.id}</span>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Dialogs */}
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
                onSuccess={() => queryClient.invalidateQueries({ queryKey: ['company', companyId] })}
              />
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
