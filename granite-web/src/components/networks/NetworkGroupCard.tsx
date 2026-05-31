'use client';

import React, { useState } from 'react';
import { NetworkCandidateGroup } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { resolveNetworkGroup } from '@/lib/api/networks';
import { toast } from 'sonner';
import { ResolveDuplicateDialog } from './ResolveDuplicateDialog';
import {
  Globe,
  Phone,
  Mail,
  Loader2,
  Copy,
  Building2,
  MapPin,
} from 'lucide-react';

interface NetworkGroupCardProps {
  group: NetworkCandidateGroup;
  onResolved: () => void;
}

const SIGNAL_CONFIG = {
  email_domain: { label: 'Домен email', icon: Mail, variant: 'default' as const },
  website: { label: 'Сайт', icon: Globe, variant: 'secondary' as const },
  phone: { label: 'Телефон', icon: Phone, variant: 'outline' as const },
};

export function NetworkGroupCard({ group, onResolved }: NetworkGroupCardProps) {
  const [loadingNetwork, setLoadingNetwork] = useState(false);
  const [showDuplicateDialog, setShowDuplicateDialog] = useState(false);

  const signal = SIGNAL_CONFIG[group.signal_type];
  const SignalIcon = signal.icon;
  const visibleCompanies = group.companies.slice(0, 3);
  const extraCount = group.companies.length - 3;

  const handleMarkNetwork = async () => {
    setLoadingNetwork(true);
    try {
      const result = await resolveNetworkGroup({ group_id: group.group_id, action: 'network' });
      toast.success(result.message || 'Группа отмечена как сеть');
      onResolved();
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    } finally {
      setLoadingNetwork(false);
    }
  };

  return (
    <>
      <div className="rounded-xl border border-border bg-card p-5 transition-shadow hover:shadow-md">
        {/* Signal header */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <SignalIcon className="h-4 w-4 text-primary" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{signal.label}</span>
                <Badge variant={signal.variant} className="text-[10px] h-4 px-1 font-mono">
                  {group.signal_value}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {group.company_count} {group.company_count === 1 ? 'компания' : 'компаний'} в группе
              </p>
            </div>
          </div>
          <Badge variant="outline" className="text-xs shrink-0">
            {group.group_id.slice(0, 8)}
          </Badge>
        </div>

        {/* Companies list */}
        <div className="space-y-2 mb-4">
          {visibleCompanies.map((company) => (
            <div
              key={company.id}
              className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground truncate">
                  {company.name}
                </span>
                <Badge variant="outline" className="text-[10px] h-4 shrink-0 font-mono">
                  ID {company.id}
                </Badge>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                <MapPin className="h-3 w-3 shrink-0" />
                <span className="truncate">{company.city}</span>
              </div>
              <div className="flex flex-wrap gap-3 mt-1 text-xs text-muted-foreground">
                {company.phones.length > 0 && (
                  <span className="inline-flex items-center gap-1">
                    <Phone className="h-3 w-3" /> {company.phones[0]}
                    {company.phones.length > 1 && <span>+{company.phones.length - 1}</span>}
                  </span>
                )}
                {company.emails.length > 0 && (
                  <span className="inline-flex items-center gap-1">
                    <Mail className="h-3 w-3" /> {company.emails[0]}
                  </span>
                )}
                {company.website && (
                  <span className="inline-flex items-center gap-1">
                    <Globe className="h-3 w-3" /> {company.website}
                  </span>
                )}
              </div>
            </div>
          ))}
          {extraCount > 0 && (
            <p className="text-xs text-muted-foreground text-center pt-1">
              +{extraCount} {extraCount === 1 ? 'ещё' : 'ещё'}
            </p>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-success/30 text-success hover:bg-success/10"
            onClick={handleMarkNetwork}
            disabled={loadingNetwork}
          >
            {loadingNetwork ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Building2 className="mr-1 h-3.5 w-3.5" />
            )}
            Это сеть
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-orange-400/30 text-orange-400 hover:bg-orange-400/10"
            onClick={() => setShowDuplicateDialog(true)}
            disabled={loadingNetwork}
          >
            <Copy className="mr-1 h-3.5 w-3.5" />
            Это дубли
          </Button>

        </div>
      </div>

      <ResolveDuplicateDialog
        group={group}
        isOpen={showDuplicateDialog}
        onClose={() => setShowDuplicateDialog(false)}
        onResolved={() => {
          setShowDuplicateDialog(false);
          onResolved();
        }}
      />
    </>
  );
}
