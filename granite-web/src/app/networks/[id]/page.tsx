'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { fetchNetworkDetail, unmarkNetwork } from '@/lib/api/networks';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Loader2, AlertCircle, ArrowLeft,
  RefreshCw, AlertTriangle, CheckCircle2, Clock,
  ChevronDown, ChevronUp, MailPlus,
} from 'lucide-react';
import { CompanySheet } from '@/components/companies/CompanySheet';
import { toast } from 'sonner';
import { useAdmin } from '@/lib/admin-context';
import { batchSpam } from '@/lib/api/admin';
import { MarkSpamDialog } from '@/components/companies/MarkSpamDialog';
import { AddToCampaignDialog } from '@/components/companies/AddToCampaignDialog';
import { NetworkEmailToggles } from '@/components/networks/NetworkEmailToggles';
import { addNetworkToCampaign, AddNetworkResult, fetchCampaigns } from '@/lib/api/campaigns';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from '@/components/ui/select';

const NETWORK_TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  franchise: { label: 'Франчайзинг', className: 'bg-[var(--network-franchise-bg)] text-[var(--network-franchise-text)] border-[var(--network-franchise-text)]/20' },
  aggregator: { label: 'Агрегатор', className: 'bg-[var(--network-aggregator-bg)] text-[var(--network-aggregator-text)] border-[var(--network-aggregator-text)]/20' },
  regional: { label: 'Региональная', className: 'bg-[var(--network-regional-bg)] text-[var(--network-regional-text)] border-[var(--network-regional-text)]/20' },
  local: { label: 'Локальная', className: 'bg-[var(--network-local-bg)] text-[var(--network-local-text)] border-[var(--network-local-text)]/20' },
};

const CONTACT_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  none: { label: 'Не отправлено', className: 'bg-[var(--contact-none-bg)] text-[var(--contact-none-text)]' },
  sent: { label: 'Отправлено', className: 'bg-[var(--contact-sent-bg)] text-[var(--contact-sent-text)]' },
};

const SEGMENT_COLORS: Record<string, string> = {
  A: 'bg-[var(--segment-a-bg)] text-white',
  B: 'bg-[var(--segment-b-bg)] text-white',
  C: 'bg-[var(--segment-c-bg)] text-white',
  D: 'bg-[var(--segment-d-bg)] text-gray-600',
  spam: 'bg-[var(--segment-spam-bg)] text-gray-400',
};

const SIGNAL_LABELS: Record<string, { label: string; className: string }> = {
  website: { label: 'Сайт', className: 'bg-primary/10 text-primary border-primary/20' },
  email_domain: { label: 'Email', className: 'bg-success/10 text-success border-success/20' },
};

export default function NetworkDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const groupId = decodeURIComponent(params.id);
  const [showConfirm, setShowConfirm] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [spamDialogOpen, setSpamDialogOpen] = useState(false);
  const [spamSaving, setSpamSaving] = useState(false);
  const [campDialogOpen, setCampDialogOpen] = useState(false);
  const [citiesOpen, setCitiesOpen] = useState(false);
  const [netCampDialogOpen, setNetCampDialogOpen] = useState(false);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const { token: adminToken, isActive: isAdmin } = useAdmin();

  // Escape key to close confirm dialog
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showConfirm) setShowConfirm(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showConfirm]);

  const { data: net, isLoading, error } = useQuery({
    queryKey: ['network-detail', groupId],
    queryFn: () => fetchNetworkDetail(groupId),
    staleTime: 10_000,
  });

  const handleUnmark = async () => {
    setShowConfirm(false);
    try {
      const result = await unmarkNetwork(groupId);
      toast.success(result.message);
      queryClient.invalidateQueries({ queryKey: ['network-detail', groupId] });
      queryClient.invalidateQueries({ queryKey: ['networks'] });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Ошибка');
    }
  };

  const handleNetworkSpam = useCallback(async (reason: string, _note?: string) => {
    if (!adminToken || !net) return;
    setSpamSaving(true);
    try {
      const ids = net.companies.map(c => c.id);
      const result = await batchSpam(ids, reason, adminToken);
      toast.success(`В спам: ${result.processed} из ${ids.length} филиалов`);
      setSpamDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ['network-detail', groupId] });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setSpamSaving(false);
    }
  }, [adminToken, net, queryClient, groupId]);

  const { data: campaignsData } = useQuery({
    queryKey: ['campaigns-selector'],
    queryFn: () => fetchCampaigns({ per_page: 200 }),
    enabled: netCampDialogOpen,
  });

  const editableCampaigns = (campaignsData?.items ?? []).filter(
    (c) => c.status === 'draft' || c.status === 'paused' || c.status === 'paused_daily_limit'
  );

  const addNetMutation = useMutation({
    mutationFn: () => {
      if (!selectedCampaignId) throw new Error('Выберите кампанию');
      return addNetworkToCampaign(selectedCampaignId, net!.id);
    },
    onSuccess: (result: AddNetworkResult) => {
      toast.success(`Добавлено: ${result.added}, пропущено: ${result.skipped}`);
      setNetCampDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ['network-detail', groupId] });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Ошибка добавления сети в кампанию';
      toast.error(msg);
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 space-y-4">
        <Loader2 className="h-10 w-10 text-primary animate-spin" />
        <p className="text-muted-foreground animate-pulse">Загрузка сети...</p>
      </div>
    );
  }

  if (error || !net) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-destructive">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="h-5 w-5" />
          <h2 className="text-lg font-semibold">Ошибка загрузки</h2>
        </div>
        <p className="mb-4">{error instanceof Error ? error.message : 'Сеть не найдена'}</p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => router.push('/networks')}>
            <ArrowLeft className="mr-1 h-4 w-4" /> К списку сетей
          </Button>
          <Button variant="outline" size="sm" onClick={() => queryClient.invalidateQueries({ queryKey: ['network-detail', groupId] })}>
            <RefreshCw className="mr-1 h-4 w-4" /> Повторить
          </Button>
        </div>
      </div>
    );
  }

  const cfg = SIGNAL_LABELS[net.signal_type] ?? SIGNAL_LABELS.website;
  const maxCount = net.top_cities[0]?.count ?? 1;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => router.push('/networks')} className="mb-2">
        <ArrowLeft className="mr-1 h-4 w-4" /> К списку сетей
      </Button>

      <Card className="overflow-hidden border-border">
        <div className="border-b bg-muted/50 py-4 px-6 flex items-stretch justify-between gap-6">
          <div className="flex flex-col justify-center space-y-1 min-w-0">
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold font-mono">{net.signal_value}</h2>
              <Badge variant="outline" size="sm" className={cfg.className}>{cfg.label}</Badge>
              <Badge variant="default" size="sm">Размечена</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Источник: <span className="font-mono text-primary">{net.signal_type}</span>
            </p>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              {net.network_type && (
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${NETWORK_TYPE_CONFIG[net.network_type]?.className ?? ''}`}>
                  {NETWORK_TYPE_CONFIG[net.network_type]?.label ?? net.network_type}
                </span>
              )}
              {net.primary_email && (
                <span className="text-xs text-muted-foreground font-mono">
                  {net.primary_email}
                </span>
              )}
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${CONTACT_STATUS_CONFIG[net.contact_status]?.className ?? ''}`}>
                {net.contact_status === 'sent' ? <CheckCircle2 className="h-3 w-3 inline mr-0.5" /> : <Clock className="h-3 w-3 inline mr-0.5" />}
                {CONTACT_STATUS_CONFIG[net.contact_status]?.label ?? net.contact_status}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCampDialogOpen(true)}
            >
              <MailPlus className="h-4 w-4 mr-1" />
              В кампанию
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSelectedCampaignId(null);
                setNetCampDialogOpen(true);
              }}
            >
              <MailPlus className="h-4 w-4 mr-1" />
              Email сети
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive border-destructive/30 hover:bg-destructive/10"
              onClick={() => setShowConfirm(true)}
            >
              Снять сеть
            </Button>
            {isAdmin && net.companies.length > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setSpamDialogOpen(true)}
              >
                <AlertTriangle className="h-4 w-4 mr-1" />
                В спам
              </Button>
            )}
          </div>
        </div>

        {showConfirm && (
          <div className="px-6 py-4 border-b border-border bg-destructive/5">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />
              <p className="text-sm flex-1">
                Убрать пометку «сеть» с {net.company_count} {net.company_count === 1 ? 'компании' : 'компаний'}?
                Это действие можно отменить повторным запуском детектора.
              </p>
              <div className="flex items-center gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={() => setShowConfirm(false)}>Отмена</Button>
                <Button variant="default" size="sm" className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={handleUnmark}>
                  Снять сеть
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-lg border border-border/60 bg-muted/30 p-4 text-center">
              <p className="text-2xl font-bold font-mono">{net.company_count}</p>
              <p className="text-xs text-muted-foreground mt-1">Филиалов</p>
            </div>
            <div className="rounded-lg border border-border/60 bg-muted/30 p-4 text-center">
              <p className="text-2xl font-bold font-mono">{net.city_count}</p>
              <p className="text-xs text-muted-foreground mt-1">Городов</p>
            </div>
            <div className="rounded-lg border border-border/60 bg-muted/30 p-4 text-center">
              <p className="text-2xl font-bold font-mono">{net.email_count}</p>
              <p className="text-xs text-muted-foreground mt-1">С email</p>
            </div>
            <div className="rounded-lg border border-border/60 bg-muted/30 p-4 text-center">
              <p className="text-2xl font-bold font-mono">{net.phone_count}</p>
              <p className="text-xs text-muted-foreground mt-1">С телефоном</p>
            </div>
            {net.sent_count > 0 && (
              <div className="rounded-lg border border-border/60 bg-muted/30 p-4 text-center">
                <p className="text-2xl font-bold font-mono text-[var(--contact-sent-text)]">{net.sent_count}/{net.total_count}</p>
                <p className="text-xs text-muted-foreground mt-1">Отправлено</p>
              </div>
            )}
          </div>
          {Object.keys(net.segment_dist ?? {}).length > 0 && (
            <div className="flex items-center gap-1.5 mt-4 flex-wrap">
              {Object.entries(net.segment_dist).sort((a, b) => b[1] - a[1]).map(([seg, count]) => (
                <span key={seg} className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${SEGMENT_COLORS[seg] ?? SEGMENT_COLORS.D}`}>
                  {seg} {count}
                </span>
              ))}
            </div>
          )}
          {net.subdomains && net.subdomains.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-xs text-muted-foreground mb-2">
                Поддомены ({net.subdomains.length})
              </p>
              <div className="flex flex-wrap gap-1">
                {net.subdomains.map((sub) => (
                  <Badge key={sub} variant="outline" className="text-xs font-mono">
                    {sub}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Email toggles */}
      <Card className="border-border p-6">
        <NetworkEmailToggles networkId={net.id} />
      </Card>

      <Card className="border-border p-6">
        <div
          className="flex items-center justify-between cursor-pointer select-none"
          onClick={() => setCitiesOpen(!citiesOpen)}
        >
          <h3 className="text-sm font-semibold">Города ({net.top_cities.length})</h3>
          <button
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label={citiesOpen ? 'Свернуть' : 'Развернуть'}
          >
            {citiesOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
        {citiesOpen && (
          <div className="mt-4">
            {net.top_cities.length > 0 ? (
              <div className="space-y-2">
                {net.top_cities.map((c, i) => (
                  <div key={c.name} className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground w-24 text-right shrink-0 truncate">{c.name}</span>
                    <div className="flex-1 h-6 rounded-md bg-muted/50 overflow-hidden">
                      <div
                        className="h-full rounded-md flex items-center justify-end pr-2 text-xs font-medium text-white"
                        style={{
                          width: `${(c.count / maxCount) * 100}%`,
                          background: 'var(--primary)',
                          opacity: 1 - i * 0.08,
                        }}
                      >
                        {c.count}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                Нет данных о распределении по городам
              </p>
            )}
          </div>
        )}
      </Card>

      <Card className="border-border overflow-hidden">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold">Филиалы ({net.companies.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/20">
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">ID</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Название</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Город</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Телефон</th>
                <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Email</th>
                <th className="text-center px-4 py-2.5 text-xs font-medium text-muted-foreground">Score</th>
              </tr>
            </thead>
            <tbody>
              {net.companies.length === 0 ? (
                <tr key="empty">
                  <td colSpan={6} className="text-center py-8 text-muted-foreground text-sm">
                    Нет данных о филиалах
                  </td>
                </tr>
              ) : net.companies.map((c) => (
                <tr key={c.id} className="border-b border-border/60 hover:bg-muted/20 transition-colors cursor-pointer" onClick={() => { setSelectedCompanyId(c.id); setSheetOpen(true); }}>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{c.id}</td>
                  <td className="px-4 py-2.5 font-medium truncate max-w-[200px]">{c.name}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{c.city}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{c.phones[0] ?? '—'}</td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground truncate max-w-[160px]">{c.emails[0] ?? '—'}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={`text-xs font-semibold font-mono ${c.score >= 4.5 ? 'text-success' : c.score >= 3 ? 'text-warning' : 'text-muted-foreground'}`}>
                      {c.score.toFixed(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Dialog open={netCampDialogOpen} onOpenChange={setNetCampDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Добавить email сети в кампанию</DialogTitle>
            <DialogDescription>
              Будут добавлены уникальные email сети ({net.email_count} шт.).
              Отключенные тогглом, уже отправленные и уже в кампании — будут пропущены.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {editableCampaigns.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                Нет кампаний в статусе draft, paused или paused_daily_limit
              </p>
            ) : (
              <Select
                value={selectedCampaignId?.toString() ?? ''}
                onValueChange={(v) => setSelectedCampaignId(Number(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите кампанию..." />
                </SelectTrigger>
                <SelectContent>
                  {editableCampaigns.map((c) => (
                    <SelectItem key={c.id} value={c.id.toString()}>
                      {c.name} ({c.status})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNetCampDialogOpen(false)}>
              Отмена
            </Button>
            <Button
              disabled={!selectedCampaignId || addNetMutation.isPending}
              onClick={() => addNetMutation.mutate()}
            >
              {addNetMutation.isPending ? 'Добавление...' : 'Добавить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AddToCampaignDialog
        open={campDialogOpen}
        onOpenChange={setCampDialogOpen}
        companyIds={net.companies.map(c => c.id)}
        count={net.companies.length}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['network-detail', groupId] });
        }}
      />
      <CompanySheet
        companyId={selectedCompanyId}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
      <MarkSpamDialog
        companyName={`сеть «${net?.signal_value ?? groupId}»`}
        isOpen={spamDialogOpen}
        onClose={() => setSpamDialogOpen(false)}
        onConfirm={handleNetworkSpam}
        isSaving={spamSaving}
      />
    </div>
  );
}
