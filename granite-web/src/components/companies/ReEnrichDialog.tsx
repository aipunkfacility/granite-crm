import React, { useState, useEffect } from 'react';
import { Company, ReEnrichPreviewResponse } from '@/lib/types/api';
import { Button } from '@/components/ui/button';
import { reEnrichPreview, reEnrichApply } from '@/lib/api/companies';
import { toast } from 'sonner';
import { Loader2, RefreshCcw, Check, X, ArrowRight } from 'lucide-react';

interface ReEnrichDialogProps {
  companyId: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ReEnrichDialog({ companyId, isOpen, onClose, onSuccess }: ReEnrichDialogProps) {
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [data, setData] = useState<ReEnrichPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadPreview();
    }
  }, [isOpen]);

  const loadPreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await reEnrichPreview(companyId);
      setData(res);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Ошибка при сканировании сайта");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!data) return;
    setApplying(true);
    try {
      await reEnrichApply(companyId, data.after);
      toast.success("Данные успешно обновлены");
      onSuccess();
      onClose();
    } catch (err: any) {
      toast.error(`Ошибка применения: ${err.message}`);
    } finally {
      setApplying(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 backdrop-blur-sm p-4">
      <div className="bg-card rounded-xl shadow-2xl w-full max-w-3xl overflow-hidden border flex flex-col max-h-[90vh]">
        <div className="p-6 border-b bg-muted flex justify-between items-center">
          <div>
            {/* V-05: font-semibold вместо font-bold */}
            <h2 className="text-xl font-semibold flex items-center">
              <RefreshCcw className="mr-2 h-5 w-5 text-primary" />
              Пересканирование сайта
            </h2>
            <p className="text-sm text-muted-foreground">Поиск актуальных контактов на официальном сайте компании</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
              <Loader2 className="h-10 w-10 text-primary animate-spin" />
              <p className="text-muted-foreground animate-pulse">Анализируем сайт компании...</p>
            </div>
          ) : error ? (
            /* V-19: red → rose (destructive palette) */
            <div className="bg-destructive/10 text-destructive p-4 rounded-lg border border-destructive/20 flex items-start">
              <X className="mr-3 h-5 w-5 mt-0.5" />
              <div>
                <p className="font-medium">Ошибка</p>
                <p className="text-sm">{error}</p>
                <Button variant="outline" size="sm" className="mt-3 text-destructive border-destructive/20" onClick={loadPreview}>
                  Попробовать снова
                </Button>
              </div>
            </div>
          ) : data ? (
            <div className="space-y-6">
              {!data.has_changes && (
                <div className="bg-amber-50 text-amber-800 p-4 rounded-lg border border-amber-100">
                  <p className="text-sm font-medium">Новых данных не обнаружено. Данные на сайте совпадают с текущими.</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-8">
                <div className="space-y-4">
                  {/* V-07,V-08: text-slate-500 font-medium */}
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-widest">Текущие данные</h3>
                  <div className="space-y-3">
                    <DataField label="Название" value={data.before.name} />
                    <DataList label="Телефоны" items={data.before.phones} />
                    <DataList label="Email" items={data.before.emails} />
                  </div>
                </div>

                <div className="space-y-4 relative">
                  <div className="absolute -left-6 top-1/2 -translate-y-1/2 text-muted-foreground">
                    <ArrowRight className="h-6 w-6" />
                  </div>
                  <h3 className="text-xs font-medium text-primary uppercase tracking-widest">Найдено на сайте</h3>
                  <div className="space-y-3">
                    <DataField
                      label="Название"
                      value={data.after.name}
                      changed={data.after.name !== data.before.name}
                    />
                    <DataList
                      label="Телефоны"
                      items={data.after.phones}
                      changed={JSON.stringify(data.after.phones) !== JSON.stringify(data.before.phones)}
                    />
                    <DataList
                      label="Email"
                      items={data.after.emails}
                      changed={JSON.stringify(data.after.emails) !== JSON.stringify(data.before.emails)}
                    />
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="p-6 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          {/* V-04: убран хардкод bg-indigo-600 — variant="default" теперь indigo через --primary */}
          <Button
            onClick={handleApply}
            disabled={applying || loading || !data?.has_changes}
          >
            {applying ? "Применение..." : "Обновить данные в CRM"}
            {!applying && <Check className="ml-2 h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

function DataField({ label, value, changed }: { label: string, value: string, changed?: boolean }) {
  return (
    <div className={`p-3 rounded-lg border transition-colors ${changed ? 'bg-primary/10 border-primary/20' : 'bg-card'}`}>
      {/* V-06: text-[10px] → text-xs */}
      <p className="text-xs text-muted-foreground uppercase mb-1">{label}</p>
      <p className={`text-sm font-medium ${changed ? 'text-primary' : ''}`}>{value || '—'}</p>
    </div>
  );
}

function DataList({ label, items, changed }: { label: string, items: string[], changed?: boolean }) {
  return (
    <div className={`p-3 rounded-lg border transition-colors ${changed ? 'bg-primary/10 border-primary/20' : 'bg-card'}`}>
      {/* V-06: text-[10px] → text-xs */}
      <p className="text-xs text-muted-foreground uppercase mb-1">{label}</p>
      <div className="space-y-1">
        {items?.length > 0 ? items.map(item => (
          <p key={item} className={`text-sm font-medium ${changed ? 'text-primary' : ''}`}>{item}</p>
        )) : <p className="text-sm text-muted-foreground italic">Нет данных</p>}
      </div>
    </div>
  );
}
