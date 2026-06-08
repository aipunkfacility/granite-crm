'use client';

import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { NetworkSummary } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Globe, Phone, Mail, Building2, MapPin, Star,
  CheckCircle2, Clock, AlertTriangle,
} from 'lucide-react';
import Link from 'next/link';
import { useAdmin } from '@/lib/admin-context';
import { toast } from 'sonner';
import { spamNetwork } from '@/lib/api/networks';
import { MarkSpamDialog } from '@/components/companies/MarkSpamDialog';
import { cn } from '@/lib/utils';

const NETWORK_TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  franchise: { label: 'Франчайзинг', className: 'bg-[var(--network-franchise-bg)] text-[var(--network-franchise-text)] border-[var(--network-franchise-text)]/20' },
  aggregator: { label: 'Агрегатор', className: 'bg-[var(--network-aggregator-bg)] text-[var(--network-aggregator-text)] border-[var(--network-aggregator-text)]/20' },
  regional: { label: 'Региональная', className: 'bg-[var(--network-regional-bg)] text-[var(--network-regional-text)] border-[var(--network-regional-text)]/20' },
  local: { label: 'Локальная', className: 'bg-[var(--network-local-bg)] text-[var(--network-local-text)] border-[var(--network-local-text)]/20' },
};

const SIGNAL_CONFIG: Record<string, { label: string; icon: React.ElementType; className: string }> = {
  website: { label: 'сайт', icon: Globe, className: 'bg-primary/10 text-primary' },
  phone: { label: 'тел', icon: Phone, className: 'bg-amber-100 text-amber-700' },
  email_domain: { label: 'email', icon: Mail, className: 'bg-emerald-100 text-emerald-700' },
};

const CONTACT_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  none: { label: 'Не отправлено', className: 'bg-[var(--contact-none-bg)] text-[var(--contact-none-text)]' },
  sent: { label: 'Отправлено', className: 'bg-[var(--contact-sent-bg)] text-[var(--contact-sent-text)]' },
};

export function NetworkCard({ net }: { net: NetworkSummary }) {
  const typeCfg = NETWORK_TYPE_CONFIG[net.network_type] ?? NETWORK_TYPE_CONFIG.franchise;
  const signalCfg = SIGNAL_CONFIG[net.signal_type] ?? SIGNAL_CONFIG.website;
  const statusCfg = CONTACT_STATUS_CONFIG[net.contact_status] ?? CONTACT_STATUS_CONFIG.none;
  const SignalIcon = signalCfg.icon;
  const { token: adminToken, isActive: isAdmin } = useAdmin();
  const queryClient = useQueryClient();
  const [spamDialogOpen, setSpamDialogOpen] = useState(false);
  const [spamSaving, setSpamSaving] = useState(false);

  const handleNetworkSpam = async (reason: string, note?: string) => {
    if (!adminToken) return;
    setSpamSaving(true);
    try {
      const result = await spamNetwork(net.group_id, reason, adminToken, note);
      toast.success(`В спам: ${result.processed} филиалов`);
      setSpamDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ['networks'] });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setSpamSaving(false);
    }
  };

  const isFranchise = net.network_type === 'franchise';
  const hasContact = Boolean(net.primary_email);

  return (
    <Link href={`/networks/${encodeURIComponent(net.group_id)}`}>
      <Card className="overflow-hidden border-border hover:shadow-md transition-shadow p-4 gap-2 cursor-pointer">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-bold font-mono truncate hover:text-primary transition-colors">
            {net.signal_value}
          </span>
          <Badge variant="outline" size="sm" className={cn('shrink-0', signalCfg.className)}>
            <SignalIcon className="h-3 w-3 mr-1" />
            {signalCfg.label}
          </Badge>
          <span className={cn(
            'text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0',
            typeCfg.className,
          )}>
            {typeCfg.label}
          </span>
          {net.primary_email && (
            <span className="text-xs text-muted-foreground truncate max-w-[200px] ml-auto hidden sm:block">
              {net.primary_email}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
          <span className="flex items-center gap-1"><Building2 className="h-3 w-3 shrink-0" /> {net.company_count} фил.</span>
          <span className="text-gray-300">·</span>
          <span className="flex items-center gap-1"><MapPin className="h-3 w-3 shrink-0" /> {net.city_count} гор.</span>
          <span className="text-gray-300">·</span>
          <span className="flex items-center gap-1"><Star className="h-3 w-3 shrink-0" /> {net.avg_score.toFixed(1)}</span>
          <span className={cn(
            'ml-auto text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0',
            statusCfg.className,
          )}>
            {net.contact_status === 'none' && <Clock className="h-3 w-3 inline mr-0.5" />}
            {net.contact_status === 'sent' && <CheckCircle2 className="h-3 w-3 inline mr-0.5" />}
            {statusCfg.label}
          </span>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-7"
            disabled={!hasContact}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            {isFranchise ? 'Выбрать филиалы' : '+ В кампанию'}
          </Button>
          {isFranchise && net.total_count > 0 && (
            <span className="text-[10px] text-muted-foreground">
              {net.sent_count}/{net.total_count}
            </span>
          )}
          {isAdmin && (
            <>
              <Button
                variant="destructive"
                size="sm"
                className="text-xs h-7 ml-auto"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setSpamDialogOpen(true);
                }}
              >
                <AlertTriangle className="h-3 w-3 mr-1" />
                В спам
              </Button>
              <MarkSpamDialog
                companyName={`сеть «${net.signal_value}»`}
                isOpen={spamDialogOpen}
                onClose={() => setSpamDialogOpen(false)}
                onConfirm={handleNetworkSpam}
                isSaving={spamSaving}
              />
            </>
          )}
        </div>
      </Card>
    </Link>
  );
}
