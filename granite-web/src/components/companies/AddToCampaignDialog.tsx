"use client";

import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";
import {
  fetchCampaigns,
  addRecipients,
  type Campaign,
} from "@/lib/api/campaigns";
import { CampaignWizard } from "@/components/campaigns/CampaignWizard";
import { toast } from "sonner";
import { AlertTriangle, Mail, Plus, X } from "lucide-react";

interface AddToCampaignDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyIds: number[];
  /** Кол-во выбранных компаний для отображения */
  count: number;
  /** Колбэк после успешного добавления */
  onSuccess?: () => void;
}

export function AddToCampaignDialog({
  open,
  onOpenChange,
  companyIds,
  count,
  onSuccess,
}: AddToCampaignDialogProps) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [confirmModeSwitch, setConfirmModeSwitch] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);

  // Загрузить черновики при открытии
  useEffect(() => {
    if (!open) return;
    setFetching(true);
    fetchCampaigns({ per_page: 100 })
      .then((res) => {
        // Только draft и paused кампании
        const editable = res.items.filter(
          (c) => c.status === "draft" || c.status === "paused" || c.status === "paused_daily_limit"
        );
        setCampaigns(editable);
      })
      .finally(() => setFetching(false));
  }, [open]);

  const selectedCampaign = campaigns.find((c) => c.id === selectedId) ?? null;

  const handleAdd = async (force: boolean) => {
    if (!selectedId) return;
    setLoading(true);
    try {
      const result = await addRecipients(selectedId, companyIds, force);
      toast.success(`Добавлено: ${result.added}, пропущено: ${result.skipped}`);
      onSuccess?.();
      onOpenChange(false);
      setSelectedId(null);
      setConfirmModeSwitch(false);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Ошибка при добавлении";
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCampaign = (campaign: Campaign) => {
    setSelectedId(campaign.id);
    // Если filter-кампания — покажем предупреждение перед добавлением
    if (campaign.recipient_mode === "filter") {
      setConfirmModeSwitch(true);
    } else {
      setConfirmModeSwitch(false);
    }
  };

  return (
    <>
      <Dialog.Root open={open} onOpenChange={onOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-foreground/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-card p-6 shadow-2xl focus:outline-none">
            <Dialog.Title className="text-lg font-semibold text-foreground">
              Добавить в кампанию
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-muted-foreground">
              Выберите кампанию для добавления {count}{" "}
              {count === 1 ? "компании" : count < 5 ? "компаний" : "компаний"}
            </Dialog.Description>

            <Dialog.Close asChild>
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-3 top-3 h-7 w-7"
              >
                <X className="h-4 w-4" />
              </Button>
            </Dialog.Close>

            {/* Предупреждение о переключении filter → manual */}
            {confirmModeSwitch && selectedCampaign && (
              <div className="mt-4 rounded-lg border border-orange-400/30 bg-orange-400/5 p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-orange-400" />
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Кампания «{selectedCampaign.name}» использует фильтры
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Добавление компаний переключит её в ручной режим. Фильтры перестанут применяться.
                    </p>
                    <div className="flex gap-2 pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setConfirmModeSwitch(false);
                          setSelectedId(null);
                        }}
                        disabled={loading}
                      >
                        Отмена
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleAdd(true)}
                        disabled={loading}
                        className="bg-orange-500 hover:bg-orange-600 text-white"
                      >
                        {loading ? "Добавление..." : "Переключить и добавить"}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {!confirmModeSwitch && (
              <div className="mt-4 space-y-3">
                {/* Кнопка «Создать новую кампанию» */}
                <button
                  className="w-full rounded-lg border-2 border-dashed border-primary/30 p-3 text-left transition-colors hover:border-primary/60 hover:bg-primary/5"
                  onClick={() => {
                    onOpenChange(false);
                    setWizardOpen(true);
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Plus className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-primary">Создать новую кампанию</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Ручной отбор · {count} {count === 1 ? "компания" : "компаний"} будет добавлено автоматически
                  </p>
                </button>

                {fetching && (
                  <p className="text-sm text-muted-foreground">Загрузка кампаний...</p>
                )}

                {!fetching && campaigns.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Или добавьте в существующую
                    </p>
                    <div className="max-h-64 space-y-2 overflow-y-auto">
                      {campaigns.map((c) => (
                        <button
                          key={c.id}
                          className={`w-full rounded-lg border p-3 text-left transition-colors ${
                            selectedId === c.id
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50"
                          }`}
                          onClick={() => handleSelectCampaign(c)}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{c.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {c.recipient_mode === "manual" ? (
                                <><Mail className="h-3 w-3 inline mr-0.5" />Ручной</>
                              ) : (
                                "Фильтр"
                              )}{" "}· {c.status}
                            </span>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {c.template_name}
                            {c.recipient_mode === "manual" && c.total_recipients != null && (
                              <span> · {c.total_recipients} получателей</span>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {!fetching && campaigns.length === 0 && (
                  <p className="text-sm text-muted-foreground py-2">
                    Нет существующих кампаний для добавления.
                  </p>
                )}
              </div>
            )}

            {/* Footer — кнопка «Добавить» только для manual-кампаний */}
            {!confirmModeSwitch && selectedId && selectedCampaign?.recipient_mode === "manual" && (
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                  disabled={loading}
                >
                  Отмена
                </Button>
                <Button onClick={() => handleAdd(false)} disabled={loading}>
                  {loading ? "Добавление..." : "Добавить"}
                </Button>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* CampaignWizard для создания новой manual-кампании */}
      <CampaignWizard
        isOpen={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onCreated={() => {
          setWizardOpen(false);
          onSuccess?.();
        }}
        preselectedCompanyIds={companyIds}
        initialRecipientMode="manual"
      />
    </>
  );
}
