'use client';

import { useState, useEffect, useCallback } from 'react';
import { useCampaignTemplates } from '@/lib/hooks/use-campaigns';
import { createCampaign, previewRecipients } from '@/lib/api/campaigns';
import { type Template } from '@/lib/api/templates';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Send,
  X,
  Loader2,
  ChevronRight,
  ChevronLeft,
  Users,
  AlertTriangle,
  FlaskConical,
  Plus,
  Check,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api/client';

/* ─── Multi-step Campaign Wizard ───
  Step 1: Название + шаблон
  Step 2: Фильтры (город, сегмент, min_score) + превью получателей
  Step 3: A/B тест (subject_a, subject_b)
  Step 4: Подтверждение
*/

interface WizardProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

const STEPS = [
  { id: 1, label: 'Шаблон', icon: Send },
  { id: 2, label: 'Фильтры', icon: Users },
  { id: 3, label: 'A/B тест', icon: FlaskConical },
  { id: 4, label: 'Подтверждение', icon: Check },
];

export function CampaignWizard({ isOpen, onClose, onCreated }: WizardProps) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);

  // Фильтры
  const [filterCity, setFilterCity] = useState('');
  const [filterSegment, setFilterSegment] = useState('');
  const [filterMinScore, setFilterMinScore] = useState('');
  const [cities, setCities] = useState<string[]>([]);

  // Превью получателей
  const [previewTotal, setPreviewTotal] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // A/B
  const [subjectA, setSubjectA] = useState('');
  const [subjectB, setSubjectB] = useState('');
  const [showVariantB, setShowVariantB] = useState(false);

  // Состояние
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: templates } = useCampaignTemplates();
  const emailTemplates = (templates || []).filter(t => t.channel === 'email');

  // Загрузка городов
  useEffect(() => {
    if (isOpen) {
      apiClient.get<{ items: string[] }>('cities', { params: { per_page: 500 } })
        .then(({ data }) => setCities(data.items || []))
        .catch(() => {});
    }
  }, [isOpen]);

  // Автозаполнение темы из шаблона
  useEffect(() => {
    if (templateName) {
      const tmpl = emailTemplates.find(t => t.name === templateName);
      setSelectedTemplate(tmpl || null);
      if (tmpl?.subject && !subjectA) {
        setSubjectA(tmpl.subject);
      }
    } else {
      setSelectedTemplate(null);
    }
  }, [templateName, emailTemplates]);

  // Превью получателей при изменении фильтров
  const loadPreview = useCallback(async () => {
    if (!templateName) return;
    setPreviewLoading(true);
    try {
      const filters: Record<string, any> = {};
      if (filterCity) filters.city = filterCity;
      if (filterSegment) filters.segment = filterSegment;
      if (filterMinScore) filters.min_score = parseInt(filterMinScore);
      const result = await previewRecipients(filters);
      setPreviewTotal(result.total);
    } catch {
      setPreviewTotal(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [templateName, filterCity, filterSegment, filterMinScore]);

  useEffect(() => {
    if (step >= 2 && isOpen) {
      const timer = setTimeout(loadPreview, 500);
      return () => clearTimeout(timer);
    }
  }, [step, isOpen, loadPreview]);

  const handleResetAndClose = () => {
    setName('');
    setTemplateName('');
    setSelectedTemplate(null);
    setFilterCity('');
    setFilterSegment('');
    setFilterMinScore('');
    setSubjectA('');
    setSubjectB('');
    setShowVariantB(false);
    setPreviewTotal(null);
    setError(null);
    setStep(1);
    onClose();
  };

  const handleCreate = async () => {
    if (!name.trim() || !templateName) return;
    setIsSaving(true);
    setError(null);
    try {
      const filters: Record<string, any> = {};
      if (filterCity) filters.city = filterCity;
      if (filterSegment) filters.segment = filterSegment;
      if (filterMinScore) filters.min_score = parseInt(filterMinScore);

      await createCampaign({
        name: name.trim(),
        template_name: templateName,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
        subject_a: subjectA || undefined,
        subject_b: showVariantB ? subjectB : undefined,
      });
      onCreated();
      handleResetAndClose();
    } catch (e: any) {
      setError(e?.message || 'Ошибка создания');
    } finally {
      setIsSaving(false);
    }
  };

  const canGoNext = () => {
    switch (step) {
      case 1: return name.trim() && templateName;
      case 2: return true;
      case 3: return !showVariantB || subjectB.trim();
      case 4: return true;
      default: return false;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden border border-border">
        {/* Header */}
        <div className="p-6 border-b bg-primary/5">
          <div className="flex items-center justify-between mb-4">
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

          {/* Step indicator */}
          <div className="flex items-center gap-2">
            {STEPS.map((s, i) => (
              <div key={s.id} className="flex items-center">
                <button
                  onClick={() => s.id < step && setStep(s.id)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                    step === s.id && "bg-primary text-primary-foreground",
                    step > s.id && "bg-primary/20 text-primary cursor-pointer",
                    step < s.id && "bg-muted text-muted-foreground"
                  )}
                >
                  <s.icon className="h-3 w-3" />
                  {s.label}
                </button>
                {i < STEPS.length - 1 && (
                  <ChevronRight className="h-3 w-3 mx-1 text-muted-foreground" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 min-h-[320px]">
          {/* Step 1: Название + Шаблон */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Название кампании</label>
                <Input
                  placeholder="Например: Холодные лиды МСК"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoFocus
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
                    Нет email-шаблонов. Создайте шаблон на странице «Шаблоны».
                  </p>
                )}
              </div>

              {/* Превью шаблона */}
              {selectedTemplate && (
                <Card className="border-border/50 bg-muted/30">
                  <CardHeader className="py-3 px-4">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5 text-primary" />
                      Превью шаблона
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-3 space-y-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">Тема:</span>{' '}
                      <span className="font-medium">{selectedTemplate.subject || '(не задана)'}</span>
                    </div>
                    <div className="text-muted-foreground line-clamp-3">
                      {selectedTemplate.body.length > 200
                        ? selectedTemplate.body.substring(0, 200) + '...'
                        : selectedTemplate.body}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* Step 2: Фильтры + превью получателей */}
          {step === 2 && (
            <div className="space-y-5">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Город</label>
                  <select
                    value={filterCity}
                    onChange={e => setFilterCity(e.target.value)}
                    className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                  >
                    <option value="">Все города</option>
                    {cities.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Сегмент</label>
                  <select
                    value={filterSegment}
                    onChange={e => setFilterSegment(e.target.value)}
                    className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                  >
                    <option value="">Все сегменты</option>
                    <option value="A">A — Горячие</option>
                    <option value="B">B — Тёплые</option>
                    <option value="C">C — Прохладные</option>
                    <option value="D">D — Холодные</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Мин. скор</label>
                  <Input
                    type="number"
                    placeholder="0"
                    min={0}
                    max={200}
                    value={filterMinScore}
                    onChange={e => setFilterMinScore(e.target.value)}
                  />
                </div>
              </div>

              {/* Превью получателей */}
              <Card className={cn(
                "border-border/50",
                previewTotal === 0 ? "bg-destructive/5 border-destructive/20" : "bg-success/5 border-success/20"
              )}>
                <CardContent className="py-4 px-4 flex items-center gap-3">
                  <Users className={cn("h-8 w-8", previewTotal === 0 ? "text-destructive" : "text-success")} />
                  <div>
                    {previewLoading ? (
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">Подсчёт получателей...</span>
                      </div>
                    ) : previewTotal !== null ? (
                      <>
                        <p className={cn("text-2xl font-bold", previewTotal === 0 ? "text-destructive" : "text-success")}>
                          {previewTotal}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {previewTotal === 0
                            ? 'Нет компаний по выбранным фильтрам'
                            : 'компаний получат письмо'}
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">Выберите фильтры для подсчёта</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Step 3: A/B тест */}
          {step === 3 && (
            <div className="space-y-5">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Тема варианта A</label>
                <Input
                  placeholder="Тема письма (вариант A)"
                  value={subjectA}
                  onChange={e => setSubjectA(e.target.value)}
                />
                {selectedTemplate?.subject && !subjectA && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Из шаблона: «{selectedTemplate.subject}»
                  </p>
                )}
              </div>

              {/* Collapsible вариант B */}
              {!showVariantB ? (
                <button
                  onClick={() => setShowVariantB(true)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-lg border-2 border-dashed border-primary/30 hover:border-primary/60 hover:bg-primary/5 transition-colors w-full text-left"
                >
                  <FlaskConical className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium text-primary">Добавить вариант B (A/B тест)</span>
                  <Plus className="h-3.5 w-3.5 text-primary/60 ml-auto" />
                </button>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FlaskConical className="h-4 w-4 text-primary" />
                      <span className="text-sm font-medium text-primary">Вариант B</span>
                      <Badge variant="outline" className="text-[10px] px-1.5">A/B тест</Badge>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs text-muted-foreground"
                      onClick={() => { setShowVariantB(false); setSubjectB(''); }}
                    >
                      Убрать вариант B
                    </Button>
                  </div>
                  <Input
                    placeholder="Тема письма (вариант B)"
                    value={subjectB}
                    onChange={e => setSubjectB(e.target.value)}
                    autoFocus
                  />
                  <p className="text-xs text-muted-foreground">
                    Компании будут разделены 50/50 между вариантами A и B.
                    Статистика по вариантам будет доступна после запуска.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 4: Подтверждение */}
          {step === 4 && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Проверьте параметры кампании</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Название</p>
                  <p className="font-medium">{name}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Шаблон</p>
                  <p className="font-mono text-primary">{templateName}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Фильтры</p>
                  <p className="font-medium">
                    {filterCity || 'Все города'} / Сегмент {filterSegment || 'Все'} / Мин. скор {filterMinScore || '0'}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border">
                  <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Получатели</p>
                  <p className="font-bold text-success">{previewTotal ?? '?'} компаний</p>
                </div>
                <div className="p-3 rounded-lg bg-muted border border-border col-span-2">
                  <p className="text-[10px] uppercase font-bold text-muted-foreground mb-1">
                    {showVariantB ? 'A/B Тест' : 'Тема письма'}
                  </p>
                  <div className="space-y-1">
                    <p><Badge variant="outline" className="text-[10px] mr-1.5">A</Badge> {subjectA || '(из шаблона)'}</p>
                    {showVariantB && (
                      <p><Badge variant="outline" className="text-[10px] mr-1.5">B</Badge> {subjectB}</p>
                    )}
                  </div>
                </div>
              </div>

              {previewTotal === 0 && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/5 border border-destructive/20">
                  <AlertTriangle className="h-4 w-4 text-destructive" />
                  <p className="text-sm text-destructive">Нет получателей по выбранным фильтрам!</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 py-3 bg-destructive/5 border-t">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Footer */}
        <div className="p-5 border-t bg-muted flex justify-between">
          <Button
            variant="ghost"
            onClick={step > 1 ? () => setStep(step - 1) : handleResetAndClose}
            disabled={isSaving}
          >
            {step > 1 ? (
              <><ChevronLeft className="mr-1 h-4 w-4" /> Назад</>
            ) : 'Отмена'}
          </Button>
          <div className="flex gap-2">
            {step < 4 ? (
              <Button
                onClick={() => setStep(step + 1)}
                disabled={!canGoNext()}
              >
                Далее <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleCreate}
                disabled={!name.trim() || !templateName || isSaving || previewTotal === 0}
                className="bg-success hover:bg-success/90 text-success-foreground"
              >
                {isSaving ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Создание...</>
                ) : (
                  <><Plus className="mr-2 h-4 w-4" /> Создать кампанию</>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
