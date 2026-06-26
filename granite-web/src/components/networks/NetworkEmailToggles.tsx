'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listNetworkEmails, toggleNetworkEmail, ToggleEmailPayload } from '@/lib/api/networks';
import { NetworkEmail } from '@/lib/types/api';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

interface NetworkEmailTogglesProps {
  networkId: number;
}

const badgeVariant = (badge: NetworkEmail['badge']): 'default' | 'destructive' | 'secondary' | 'outline' => {
  switch (badge) {
    case 'sent': return 'default';
    case 'bounced': return 'destructive';
    case 'disabled': return 'secondary';
    default: return 'outline';
  }
};

const badgeLabel = (badge: NetworkEmail['badge']): string => {
  switch (badge) {
    case 'sent': return 'Отправлено';
    case 'bounced': return 'Bounced';
    case 'disabled': return 'Отключен';
    default: return '';
  }
};

export function NetworkEmailToggles({ networkId }: NetworkEmailTogglesProps) {
  const queryClient = useQueryClient();

  const { data: emails, isLoading } = useQuery({
    queryKey: ['network-emails', networkId],
    queryFn: () => listNetworkEmails(networkId),
  });

  const toggleMutation = useMutation({
    mutationFn: (payload: ToggleEmailPayload) =>
      toggleNetworkEmail(networkId, payload),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: ['network-emails', networkId] });
      const previous = queryClient.getQueryData<NetworkEmail[]>(['network-emails', networkId]);
      queryClient.setQueryData<NetworkEmail[]>(['network-emails', networkId], (old) =>
        old?.map((e) =>
          e.email === payload.email ? { ...e, is_disabled: payload.is_disabled } : e
        ) ?? old
      );
      return { previous };
    },
    onSuccess: (result) => {
      toast.success(result.message);
      queryClient.invalidateQueries({ queryKey: ['network-emails', networkId] });
    },
    onError: (error: unknown, _payload, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['network-emails', networkId], context.previous);
      }
      const msg = error instanceof Error ? error.message : 'Ошибка';
      toast.error(msg);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!emails || emails.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground">
        Email сети ({emails.length})
      </h3>
      <div className="space-y-1">
        {emails.map((item) => (
          <div
            key={item.email}
            className="flex items-center gap-3 p-2 rounded-lg border bg-card"
          >
            <Switch
              checked={!item.is_disabled}
              onCheckedChange={(checked) =>
                toggleMutation.mutate({
                  email: item.email,
                  is_disabled: !checked,
                })
              }
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-mono truncate">{item.email}</p>
              {item.reason && (
                <p className="text-xs text-muted-foreground">{item.reason}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {item.sent_count > 0 && (
                <span className="text-xs text-muted-foreground">
                  {item.sent_count} отправок
                </span>
              )}
              {item.badge && (
                <Badge variant={badgeVariant(item.badge)} className="text-xs">
                  {badgeLabel(item.badge)}
                </Badge>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
