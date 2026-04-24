'use client';

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchCompany, updateCompany, markSpam, unmarkSpam } from "@/lib/api/companies";
import * as Dialog from "@radix-ui/react-dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
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
  ShieldOff,
  ShieldAlert,
  Shield,
  Ban,
  Undo2,
} from "lucide-react";
import { FUNNEL_STAGES, SEGMENT_CONFIG } from "@/constants/funnel";
import { FunnelStage } from "@/lib/types/api";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { useDebouncedCallback } from "use-debounce";
import { CompanyEditDialog } from "@/components/companies/CompanyEditDialog";
import { ReEnrichDialog } from "@/components/companies/ReEnrichDialog";
import { MarkSpamDialog } from "@/components/companies/MarkSpamDialog";

/* V-01: Карточка компании — Sheet (side panel) вместо отдельной страницы */

/* TG Trust Indicator — детальный статус «живости» Telegram в Sheet */
function TgTrustIndicator({ trust }: { trust: Record<string, any> }) {
  const score = trust?.trust_score;
  if (score === undefined || score === null) return null;

  const config: Record<number, { icon: React.ElementType; color: string; bg: string; label: string }> = {
    0: { icon: ShieldOff, color: 'text-destructive', bg: 'bg-destructive/10', label: 'Мёртвый' },
    1: { icon: ShieldAlert, color: 'text-orange-400', bg: 'bg-orange-400/10', label: 'Частичный' },
    2: { icon: Shield, color: 'text-info', bg: 'bg-info/10', label: 'Живой' },
    3: { icon: ShieldCheck, color: 'text-success', bg: 'bg-success/10', label: 'Активный' },
  };

  const { icon: Icon, color, bg, label } = config[score] ?? config[0];
  const hasAvatar = trust?.has_avatar;
  const hasBio = trust?.has_bio;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${bg} ${color}`} title={`TG Trust: ${score}/3\nAvatar: ${hasAvatar ? 'да' : 'нет'}\nBio: ${hasBio ? 'да' : 'нет'}`}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

interface CompanySheetProps {
  companyId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CompanySheet({ companyId, open, onOpenChange }: CompanySheetProps) {
  const queryClient = useQueryClient();

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isReEnrichOpen, setIsReEnrichOpen] = useState(false);
  const [isSpamDialogOpen, setIsSpamDialogOpen] = useState(false);

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

  /* Mark-spam с undo toast */
  const handleMarkSpam = async (reason: string, note?: string) => {
    if (!companyId) return;
    try {
      await markSpam(companyId, reason, note);
      setIsSpamDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('Компания перемещена в спам', {
        duration: 5000,
        action: {
          label: 'Отменить',
          onClick: () => handleUnmarkSpam(),
        },
      });
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    }
  };

  /* Unmark-spam — восстановление */
  const handleUnmarkSpam = async () => {
    if (!companyId) return;
    try {
      await unmarkSpam(companyId);
      queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('Компания восстановлена из спама');
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    }
  };

  if (!companyId) return null;

  const stage = company ? FUNNEL_STAGES[company.funnel_stage] : null;
  const segment = company?.segment ? SEGMENT_CONFIG[company.segment] : null;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-foreground/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed inset-y-0 right-0 z-50 w-full max-w-xl border-l bg-card shadow-2xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right duration-300 flex flex-col focus:outline-none"
        >
          <VisuallyHidden>
            <Dialog.Title>{company?.name ?? "Карточка компании"}</Dialog.Title>
            <Dialog.Description>Карточка компании с контактами, воронкой и заметками</Dialog.Description>
          </VisuallyHidden>
          {/* Header */}
          {isLoading ? (
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div className="h-6 w-48 animate-pulse rounded bg-muted" />
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
              <div className="flex items-center justify-between border-b px-6 py-4 bg-muted/50">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="min-w-0">
                    {/* V-05: font-semibold, not font-bold — Dialog.Title moved to VisuallyHidden for a11y */}
                    <span className="text-lg font-semibold text-foreground truncate">
                      {company.name}
                    </span>
                    <div className="flex items-center text-sm text-muted-foreground mt-0.5">
                      <MapPin className="mr-1 h-3 w-3 shrink-0" />
                      <span className="truncate">{company.city}, {company.region}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0 ml-3">
                  {company.segment === 'spam' ? (
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full border-success/30 hover:bg-success/10 hover:text-success"
                      onClick={handleUnmarkSpam}
                      title="Восстановить из спама"
                    >
                      <Undo2 className="h-3.5 w-3.5" />
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => setIsSpamDialogOpen(true)}
                      title="В спам"
                    >
                      <Ban className="h-3.5 w-3.5" />
                    </Button>
                  )}
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

              {/* Spam banner */}
              {company.segment === 'spam' && (
                <div className="px-6 py-2 bg-destructive/5 border-b border-destructive/20">
                  <div className="flex items-center gap-2 text-sm text-destructive">
                    <Ban className="h-4 w-4 shrink-0" />
                    <span className="font-medium">Компания в спаме</span>
                    <span className="text-destructive/70">— автоматизация остановлена</span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="ml-auto text-destructive border-destructive/20 hover:bg-destructive/10"
                      onClick={handleUnmarkSpam}
                    >
                      <Undo2 className="mr-1 h-3 w-3" /> Восстановить
                    </Button>
                  </div>
                </div>
              )}

              {/* Scrollable body */}
              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                {/* Segment & Score */}
                <div className="flex gap-2 flex-wrap">
                  {segment && (
                    <Badge variant={segment.variant} className="px-3 py-1 shadow-sm">
                      Сегмент {segment.label}
                    </Badge>
                  )}
                  <Badge variant="outline" className="px-3 py-1 font-mono-code bg-card shadow-sm">
                    Score: {company.crm_score}
                  </Badge>
                </div>

                {/* Contacts + Messengers */}
                <div className="grid grid-cols-1 gap-5">
                  <div className="space-y-3">
                    {/* V-07, V-08: labels text-slate-500 font-medium */}
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-widest">Контакты</h3>
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
                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-widest">Мессенджеры</h3>
                    <div className="flex flex-wrap gap-2">
                      {company.telegram && (
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" asChild className="border-info/20 hover:bg-info/10">
                            <a href={company.telegram.startsWith('http') ? company.telegram : `https://t.me/${company.telegram.replace('@', '')}`} target="_blank" rel="noreferrer">
                              <Send className="mr-2 h-4 w-4 text-info" /> Telegram
                            </a>
                          </Button>
                          <TgTrustIndicator trust={company.tg_trust} />
                        </div>
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

                {/* CMS / Сеть / Quiz tiles */}
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-muted border border-border">
                    {/* V-06: text-[10px] → text-xs, V-07: text-slate-400→500, V-08: font-semibold→font-medium */}
                    <p className="text-muted-foreground mb-1 font-medium uppercase tracking-wider">CMS</p>
                    <p className="font-medium text-foreground">{company.cms || 'НЕ ОПРЕДЕЛЕНО'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-muted border border-border">
                    <p className="text-muted-foreground mb-1 font-medium uppercase tracking-wider">СЕТЬ</p>
                    <p className="font-medium text-foreground flex items-center">
                      {company.is_network ? <ShieldCheck className="mr-1 h-3 w-3 text-success" /> : <Building className="mr-1 h-3 w-3 text-muted-foreground" />}
                      {company.is_network ? 'ДА' : 'НЕТ'}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-muted border border-border">
                    <p className="text-muted-foreground mb-1 font-medium uppercase tracking-wider">КВИЗ MARQUIZ</p>
                    <p className="font-medium text-foreground">{company.has_marquiz ? 'ЕСТЬ' : 'НЕТ'}</p>
                  </div>
                </div>

                {/* Notes */}
                <Card className="border-border">
                  <CardHeader className="border-b pb-3 flex flex-row items-center justify-between">
                    {/* V-20: CardTitle font-semibold */}
                    <CardTitle className="text-sm font-semibold">Заметки</CardTitle>
                    <div className="text-xs font-medium text-muted-foreground">
                      {updateMutation.isPending ? "Сохранение..." : "Автосохранение"}
                    </div>
                  </CardHeader>
                  <CardContent className="pt-4">
                    <Textarea
                      placeholder="Добавьте важную информацию о компании..."
                      className="min-h-[160px] resize-none border-none p-0 focus-visible:ring-0 text-foreground leading-relaxed"
                      value={notes}
                      onChange={(e) => {
                        setNotes(e.target.value);
                        debouncedSaveNotes(e.target.value);
                      }}
                    />
                  </CardContent>
                </Card>

                {/* Funnel */}
                <Card className="border-primary/20 bg-primary/10 shadow-sm shadow-primary/10">
                  <CardHeader className="pb-3">
                    {/* V-20: CardTitle font-semibold */}
                    <CardTitle className="text-sm font-semibold flex items-center text-primary">
                      <CheckCircle2 className="mr-2 h-4 w-4 text-primary" />
                      Воронка продаж
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      {/* V-06,V-07,V-08: indigo context labels — keep indigo-400 but use text-xs font-medium */}
                      <p className="text-xs font-medium text-primary/60 uppercase tracking-widest">Текущая стадия</p>
                      <Badge variant={stage!.variant} className="w-full justify-center py-2.5 text-xs font-bold uppercase tracking-widest bg-card shadow-sm">
                        {stage!.label}
                      </Badge>
                    </div>

                    <div className="pt-3 space-y-2">
                      <p className="text-xs font-medium text-primary/60 uppercase tracking-widest mb-2">Сменить стадию</p>
                      <div className="grid grid-cols-1 gap-1.5">
                        {(Object.keys(FUNNEL_STAGES) as FunnelStage[]).map((s) => (
                          <Button
                            key={s}
                            variant={company.funnel_stage === s ? "default" : "outline"}
                            size="sm"
                            /* V-04: убран хардкод bg-indigo-600 — теперь variant="default" даёт indigo через --primary */
                            className={`justify-start font-medium text-xs h-9 ${company.funnel_stage === s ? '' : 'bg-card border-primary/20 text-primary hover:bg-primary/10'}`}
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

                    <div className="pt-4 mt-3 border-t border-primary/20 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-primary">Стоп-автоматизация</span>
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

                {/* Activity */}
                <Card className="border-border">
                  <CardHeader className="pb-3 border-b">
                    {/* V-20: CardTitle font-semibold */}
                    <CardTitle className="text-sm font-semibold">Активность</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 pt-3 text-sm font-medium text-foreground">
                    <div className="flex justify-between items-center p-2 rounded-lg bg-muted border border-border">
                      <div className="flex items-center">
                        <Mail className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
                        Email отправлено
                      </div>
                      <span className="text-primary font-bold">{company.email_sent_count}</span>
                    </div>
                    <div className="flex justify-between items-center p-2 rounded-lg bg-success/10 border border-success/20">
                      <div className="flex items-center">
                        <CheckCircle2 className="h-3.5 w-3.5 mr-2 text-success" />
                        Email открыто
                      </div>
                      <span className="text-success font-bold">{company.email_opened_count}</span>
                    </div>
                    <div className="flex justify-between items-center p-2 rounded-lg bg-info/10 border border-info/20">
                      <div className="flex items-center">
                        <MessageSquare className="h-3.5 w-3.5 mr-2 text-info" />
                        Мессенджеры
                      </div>
                      <span className="text-info font-bold">{company.tg_sent_count + company.wa_sent_count}</span>
                    </div>
                    {/* V-06,V-07: text-[10px] → text-xs, text-slate-400 → text-slate-500 */}
                    <div className="pt-3 text-xs text-muted-foreground uppercase tracking-widest flex justify-between">
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

              <MarkSpamDialog
                companyName={company.name}
                isOpen={isSpamDialogOpen}
                onClose={() => setIsSpamDialogOpen(false)}
                onConfirm={handleMarkSpam}
                isSaving={false}
              />
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
