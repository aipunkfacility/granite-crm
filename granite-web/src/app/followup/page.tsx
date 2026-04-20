'use client';

import { useFollowup } from "@/lib/hooks/use-followup";
import { recordTouch } from "@/lib/api/followup";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { 
  Mail, 
  Send, 
  MessageSquare, 
  CheckCircle2, 
  ExternalLink,
  Clock,
  ArrowRight
} from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { SEGMENT_CONFIG } from "@/constants/funnel";

export default function FollowupPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useFollowup();

  const touchMutation = useMutation({
    mutationFn: ({ id, channel }: { id: number; channel: string }) => recordTouch(id, channel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['followup'] });
      toast.success("Касание записано, компания перемещена в конец очереди");
    },
    onError: (err: Error) => {
      toast.error(`Ошибка: ${err.message}`);
    }
  });

  if (isLoading) return (
    <div className="space-y-4">
      <div className="h-8 w-64 bg-slate-100 animate-pulse rounded" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1,2,3,4].map(i => <div key={i} className="h-40 w-full bg-slate-100 animate-pulse rounded" />)}
      </div>
    </div>
  );

  if (error) return <div className="p-8 text-destructive">Ошибка: {(error as Error).message}</div>;

  const items = data?.items || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Очередь Follow-up</h1>
        <p className="text-slate-500">
          Компании, которые ждут вашего внимания. Список отсортирован по приоритету.
        </p>
      </div>

      {items.length === 0 ? (
        <Card className="border-dashed py-12">
          <CardContent className="flex flex-col items-center justify-center text-center">
            <CheckCircle2 className="h-12 w-12 text-emerald-500 mb-4" />
            <h2 className="text-xl font-semibold text-slate-900">Все дожаты!</h2>
            <p className="text-slate-500 max-w-sm mt-2">
              На сегодня больше нет компаний, требующих немедленного контакта.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {items.map((item) => {
            const segment = item.segment ? SEGMENT_CONFIG[item.segment as any] : null;
            
            return (
              <Card key={item.company_id} className="group hover:border-indigo-200 transition-colors">

                <CardContent className="p-5 flex flex-col h-full justify-between gap-4">
                  <div className="space-y-3">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <Link 
                          href={`/companies/${item.company_id}`}
                          className="text-lg font-bold text-slate-900 hover:text-indigo-600 flex items-center gap-1"
                        >
                          {item.name}
                          <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </Link>
                        <p className="text-xs text-slate-500 flex items-center">
                          <Clock className="mr-1 h-3 w-3" />
                          Связь: {item.next_followup_at 
                            ? formatDistanceToNow(new Date(item.next_followup_at), { addSuffix: true, locale: ru })
                            : 'Срочно'}
                        </p>
                      </div>
                      {segment && <Badge variant={segment.variant}>{segment.label}</Badge>}
                    </div>

                    <div className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                      <div className="flex items-center gap-2 text-indigo-700 font-medium text-sm mb-1">
                        <ArrowRight className="h-4 w-4" />
                        Что сделать:
                      </div>
                      <p className="text-sm text-slate-700">{item.action_suggested}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    {item.channel_suggested === 'tg' && (
                      <Button 
                        size="sm" 
                        className="bg-sky-500 hover:bg-sky-600 flex-1"
                        onClick={() => {
                          window.open(`https://t.me/${item.contact_data.replace('@', '')}`, '_blank');
                          touchMutation.mutate({ id: item.company_id, channel: 'tg' });
                        }}
                      >
                        <Send className="mr-2 h-4 w-4" /> Telegram
                      </Button>
                    )}
                    {item.channel_suggested === 'wa' && (
                      <Button 
                        size="sm" 
                        className="bg-emerald-500 hover:bg-emerald-600 flex-1"
                        onClick={() => {
                          window.open(`https://wa.me/${item.contact_data}`, '_blank');
                          touchMutation.mutate({ id: item.company_id, channel: 'wa' });
                        }}
                      >
                        <MessageSquare className="mr-2 h-4 w-4" /> WhatsApp
                      </Button>
                    )}
                    {item.channel_suggested === 'email' && (
                      <Button 
                        size="sm" 
                        className="bg-indigo-500 hover:bg-indigo-600 flex-1"
                        onClick={() => {
                          window.location.href = `mailto:${item.contact_data}`;
                          touchMutation.mutate({ id: item.company_id, channel: 'email' });
                        }}
                      >
                        <Mail className="mr-2 h-4 w-4" /> Email
                      </Button>
                    )}
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => touchMutation.mutate({ id: item.company_id, channel: 'manual' })}
                      disabled={touchMutation.isPending}
                    >
                      <CheckCircle2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
