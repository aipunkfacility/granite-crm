'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { type Touch } from '@/lib/types/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Mail,
  Phone,
  MessageSquare,
  Send,
  ArrowDownLeft,
  ArrowUpRight,
  Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

interface TouchHistoryProps {
  companyId: number;
}

const CHANNEL_ICONS: Record<string, any> = {
  email: Mail,
  tg: Send,
  wa: MessageSquare,
  manual: Phone,
};

const DIRECTION_CONFIG = {
  outgoing: { icon: ArrowUpRight, label: 'Исходящее', color: 'text-primary' },
  incoming: { icon: ArrowDownLeft, label: 'Входящее', color: 'text-success' },
};

export function TouchHistory({ companyId }: TouchHistoryProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['touches', companyId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: Touch[]; total: number }>(
        `companies/${companyId}/touches`,
        { params: { per_page: 20 } }
      );
      return data;
    },
  });

  const touches = data?.items || [];

  if (isLoading) {
    return (
      <Card className="border-border">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          Загрузка истории...
        </CardContent>
      </Card>
    );
  }

  if (touches.length === 0) {
    return (
      <Card className="border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Clock className="h-4 w-4" />
            История касаний
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground italic">Нет записей о касаниях</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Clock className="h-4 w-4" />
          История касаний
          <Badge variant="outline" className="text-[10px] px-1.5">
            {data?.total || 0}{(data?.total || 0) > 20 ? ` (показано ${touches.length})` : ''}  {/* P4R-L19 */}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {touches.map((touch) => {
          const ChannelIcon = CHANNEL_ICONS[touch.channel] || Mail;
          const dirConfig = DIRECTION_CONFIG[touch.direction as keyof typeof DIRECTION_CONFIG] || DIRECTION_CONFIG.outgoing;
          const DirIcon = dirConfig.icon;

          return (
            <div key={touch.id} className="flex items-start gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors">
              <div className={cn("flex-shrink-0 mt-0.5", dirConfig.color)}>
                <DirIcon className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <ChannelIcon className="h-3 w-3 text-muted-foreground" />
                  <span className="text-xs font-medium truncate">{touch.subject || '(без темы)'}</span>
                </div>
                {touch.body && (
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{touch.body.substring(0, 150)}</p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="outline" className="text-[9px] px-1 py-0">{touch.channel}</Badge>
                  {touch.template_name && (
                    <Badge variant="outline" className="text-[9px] px-1 py-0 bg-primary/10 text-primary border-primary/20">
                      {touch.template_name}
                    </Badge>
                  )}
                  <span className="text-[10px] text-muted-foreground">
                    {/* P4R-M24: try/catch для невалидных дат */}
                    {(() => {
                      if (!touch.created_at) return '';
                      try {
                        return format(new Date(touch.created_at), 'd MMM, HH:mm', { locale: ru });
                      } catch {
                        return touch.created_at;
                      }
                    })()}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
