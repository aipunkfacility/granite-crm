'use client';

import { useCampaigns } from '@/lib/hooks/use-campaigns';
import { runCampaign, pauseCampaign, deleteCampaign } from '@/lib/api/campaigns';
import { CampaignCard } from '@/components/campaigns/CampaignCard';
import { CampaignWizard } from '@/components/campaigns/CampaignWizard';
import { CampaignDashboard } from '@/components/campaigns/CampaignDashboard';
import { Button } from '@/components/ui/button';
import {
  Mail,
  Plus,
} from 'lucide-react';
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export default function CampaignsPage() {
  const { data, isLoading } = useCampaigns();
  const campaigns = data?.items || [];
  const [createOpen, setCreateOpen] = useState(false);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [pausingId, setPausingId] = useState<number | null>(null);
  const [dashboardId, setDashboardId] = useState<number | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const handleRun = async (id: number) => {
    setRunningId(id);
    try {
      await runCampaign(id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Ошибка запуска');
    } finally {
      setRunningId(null);
    }
  };

  const handlePause = async (id: number) => {
    setPausingId(id);
    try {
      await pauseCampaign(id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Ошибка паузы');
    } finally {
      setPausingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteCampaign(id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      toast.success('Черновик удалён');
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Ошибка удаления');
    } finally {
      setDeleteConfirmId(null);
    }
  };

  if (dashboardId !== null) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => setDashboardId(null)}>
          ← Назад к списку кампаний
        </Button>
        <CampaignDashboard
          campaignId={dashboardId}
          onClose={() => setDashboardId(null)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Кампании</h1>
          <p className="text-muted-foreground">Управление массовыми email-рассылками и отслеживание прогресса.</p>
        </div>
        <Button className="bg-primary" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> Создать кампанию
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map(i => <div key={i} className="h-56 w-full bg-muted animate-pulse rounded-xl" />)}
        </div>
      ) : campaigns.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed rounded-xl bg-muted/50">
          <Mail className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-medium text-foreground">Нет активных кампаний</h3>
          <p className="text-muted-foreground mt-1">Создайте свою первую рассылку, чтобы начать привлекать клиентов.</p>
          <Button className="mt-4" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> Создать кампанию
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {campaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onOpenDashboard={() => setDashboardId(campaign.id)}
              onRun={() => handleRun(campaign.id)}
              onPause={() => handlePause(campaign.id)}
              onDelete={() => handleDelete(campaign.id)}
              isRunning={runningId === campaign.id}
              isPausing={pausingId === campaign.id}
              deleteConfirmActive={deleteConfirmId === campaign.id}
              onRequestDeleteConfirm={() => setDeleteConfirmId(campaign.id)}
              onCancelDeleteConfirm={() => setDeleteConfirmId(null)}
            />
          ))}
        </div>
      )}

      <CampaignWizard
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ['campaigns'] })}
      />
    </div>
  );
}
