'use client';

import React, { useState } from 'react';
import { Company } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { resolveReview, ResolveReviewPayload, markSpam } from '@/lib/api/companies';
import { FUNNEL_STAGES, SEGMENT_CONFIG } from '@/constants/funnel';
import { toast } from 'sonner';
import {
  CheckCircle2,
  Ban,
  Copy,
  MapPin,
  Globe,
  Phone,
  Mail,
  Send,
  ShieldOff,
  ShieldAlert,
  Shield,
  ShieldCheck,
  ChevronRight,
  Loader2,
} from 'lucide-react';

interface ReviewCardProps {
  company: Company;
  onResolved: () => void;
  /** Показывать ли фокус (текущая карточка) */
  focused?: boolean;
}

const SPAM_REASONS = [
  { value: 'aggregator', label: 'Агрегатор' },
  { value: 'closed', label: 'Закрылась' },
  { value: 'wrong_category', label: 'Не та категория' },
  { value: 'duplicate_contact', label: 'Дубликат контактов' },
  { value: 'other', label: 'Другое' },
];

/* TG Trust mini-badge для review-карточки */
function TgTrustMini({ trust }: { trust: Record<string, any> }) {
  const score = trust?.trust_score;
  if (score === undefined || score === null) return null;
  const config: Record<number, { icon: React.ElementType; color: string }> = {
    0: { icon: ShieldOff, color: 'text-destructive' },
    1: { icon: ShieldAlert, color: 'text-orange-400' },
    2: { icon: Shield, color: 'text-info' },
    3: { icon: ShieldCheck, color: 'text-success' },
  };
  const { icon: Icon, color } = config[score] ?? config[0];
  return <Icon className={`h-3.5 w-3.5 ${color}`} />;
}

export function ReviewCard({ company, onResolved, focused }: ReviewCardProps) {
  const [loading, setLoading] = useState(false);
  const [showSpamReasons, setShowSpamReasons] = useState(false);

  const segment = company.segment ? SEGMENT_CONFIG[company.segment] : null;
  const stage = FUNNEL_STAGES[company.funnel_stage];

  const handleResolve = async (payload: ResolveReviewPayload) => {
    setLoading(true);
    try {
      await resolveReview(company.id, payload);
      toast.success(
        payload.action === 'approve' ? 'Подтверждено' :
        payload.action === 'spam' ? 'В спам' : 'Помечено как дубль'
      );
      onResolved();
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSpam = async (reason: string) => {
    setLoading(true);
    try {
      await resolveReview(company.id, { action: 'spam', reason });
      toast.success('Перемещено в спам');
      onResolved();
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    } finally {
      setLoading(false);
      setShowSpamReasons(false);
    }
  };

  return (
    <div
      className={`rounded-xl border bg-card p-5 transition-shadow ${
        focused ? 'border-primary/40 shadow-md shadow-primary/5' : 'border-border'
      }`}
    >
      {/* Header: name + reason badge */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-foreground truncate">{company.name}</h3>
          <div className="flex items-center gap-2 text-sm text-muted-foreground mt-0.5">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">{company.city}, {company.region}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {segment && (
            <Badge variant={segment.variant} className="text-xs">{segment.label}</Badge>
          )}
          <Badge variant="outline" className="font-mono-code text-xs">{company.crm_score}</Badge>
        </div>
      </div>

      {/* Review reason */}
      {company.review_reason && (
        <div className="mb-3 px-3 py-2 rounded-lg bg-amber-400/10 border border-amber-400/20 text-xs text-amber-600 dark:text-amber-400">
          <span className="font-medium">Причина проверки:</span>{' '}
          {company.review_reason}
        </div>
      )}

      {/* Contacts row */}
      <div className="flex flex-wrap gap-3 mb-4 text-sm">
        {company.phones.length > 0 && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Phone className="h-3.5 w-3.5" /> {company.phones[0]}
          </span>
        )}
        {company.emails.length > 0 && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Mail className="h-3.5 w-3.5" /> {company.emails[0]}
          </span>
        )}
        {company.website && (
          <a href={company.website} target="_blank" rel="noreferrer"
             className="inline-flex items-center gap-1 text-info hover:underline">
            <Globe className="h-3.5 w-3.5" /> Сайт
          </a>
        )}
        {company.telegram && (
          <span className="inline-flex items-center gap-1 text-info">
            <Send className="h-3.5 w-3.5" /> TG
            <TgTrustMini trust={company.tg_trust} />
          </span>
        )}
        <Badge variant={stage.variant} className="text-xs h-5">{stage.label}</Badge>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="border-success/30 text-success hover:bg-success/10"
          onClick={() => handleResolve({ action: 'approve' })}
          disabled={loading}
        >
          {loading ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="mr-1 h-3.5 w-3.5" />}
          Подтвердить
          <kbd className="ml-2 hidden sm:inline-flex h-4 items-center rounded border border-border px-1 text-[10px] text-muted-foreground">A</kbd>
        </Button>

        {!showSpamReasons ? (
          <Button
            variant="outline"
            size="sm"
            className="border-destructive/30 text-destructive hover:bg-destructive/10"
            onClick={() => setShowSpamReasons(true)}
            disabled={loading}
          >
            <Ban className="mr-1 h-3.5 w-3.5" />
            В спам
            <kbd className="ml-2 hidden sm:inline-flex h-4 items-center rounded border border-border px-1 text-[10px] text-muted-foreground">S</kbd>
          </Button>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {SPAM_REASONS.map(r => (
              <Button
                key={r.value}
                variant="outline"
                size="sm"
                className="h-7 text-xs border-destructive/20 text-destructive hover:bg-destructive/10"
                onClick={() => handleQuickSpam(r.value)}
                disabled={loading}
              >
                {r.label}
              </Button>
            ))}
          </div>
        )}

        <Button
          variant="outline"
          size="sm"
          className="border-orange-400/30 text-orange-400 hover:bg-orange-400/10 ml-auto"
          onClick={() => handleResolve({ action: 'duplicate' })}
          disabled={loading}
        >
          <Copy className="mr-1 h-3.5 w-3.5" />
          Дубль
          <kbd className="ml-2 hidden sm:inline-flex h-4 items-center rounded border border-border px-1 text-[10px] text-muted-foreground">D</kbd>
        </Button>
      </div>
    </div>
  );
}
