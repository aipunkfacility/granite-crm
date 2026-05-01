"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  fetchCampaigns,
  addRecipients,
  type Campaign,
} from "@/lib/api/campaigns";
import { useToast } from "@/hooks/use-toast";

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
  const { toast } = useToast();

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

  const handleAdd = async () => {
    if (!selectedId) return;
    setLoading(true);
    try {
      const result = await addRecipients(selectedId, companyIds, true);
      toast({
        title: "Компании добавлены",
        description: `Добавлено: ${result.added}, пропущено: ${result.skipped}`,
      });
      onSuccess?.();
      onOpenChange(false);
      setSelectedId(null);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Ошибка при добавлении";
      toast({ title: "Ошибка", description: detail, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Добавить в кампанию</DialogTitle>
          <DialogDescription>
            Выберите кампанию для добавления {count}{" "}
            {count === 1 ? "компании" : count < 5 ? "компаний" : "компаний"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {fetching && (
            <p className="text-sm text-muted-foreground">Загрузка кампаний...</p>
          )}

          {!fetching && campaigns.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Нет доступных кампаний (нужен статус «Черновик» или «На паузе»).
              Сначала создайте кампанию.
            </p>
          )}

          {!fetching && campaigns.length > 0 && (
            <div className="max-h-64 space-y-2 overflow-y-auto">
              {campaigns.map((c) => (
                <button
                  key={c.id}
                  className={`w-full rounded-lg border p-3 text-left transition-colors ${
                    selectedId === c.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  }`}
                  onClick={() => setSelectedId(c.id)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{c.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.recipient_mode === "manual" ? "Ручной" : "Фильтр"} · {c.status}
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
          )}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            Отмена
          </Button>
          <Button onClick={handleAdd} disabled={!selectedId || loading}>
            {loading ? "Добавление..." : "Добавить"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
