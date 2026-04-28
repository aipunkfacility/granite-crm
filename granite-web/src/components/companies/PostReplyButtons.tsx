'use client';

import { useState } from 'react';
import { previewReply, sendReply, type ReplyPreview } from '@/lib/api/replies';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  Reply,
  DollarSign,
  Image,
  Clock,
  ShieldCheck,
  XCircle,
  Eye,
  Send,
  Loader2,
  X,
  ChevronDown,
  ChevronUp,
  Mail,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

/* ─── Post-reply кнопки ───
  Playbook-шаблоны для быстрого ответа на карточке компании.
  Кнопки: «Цена», «Примеры», «Сроки», «Есть подрядчик», «Отказ»
*/

interface PostReplyButtonsProps {
  companyId: number;
  hasEmail: boolean;
  funnelStage: string;
  templateNames: string[];
}

const PLAYBOOK_BUTTONS = [
  { template: 'reply_price', label: 'Цена', icon: DollarSign, color: 'text-success hover:bg-success/10 border-success/20' },
  { template: 'reply_examples', label: 'Примеры', icon: Image, color: 'text-info hover:bg-info/10 border-info/20' },
  { template: 'reply_deadline', label: 'Сроки', icon: Clock, color: 'text-amber-600 hover:bg-amber-50 border-amber-200' },
  { template: 'reply_has_contractor', label: 'Есть подрядчик', icon: ShieldCheck, color: 'text-purple-600 hover:bg-purple-50 border-purple-200' },
  { template: 'reply_rejection', label: 'Отказ', icon: XCircle, color: 'text-destructive hover:bg-destructive/10 border-destructive/20' },
];

export function PostReplyButtons({ companyId, hasEmail, funnelStage, templateNames }: PostReplyButtonsProps) {
  const [previewData, setPreviewData] = useState<ReplyPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [subjectOverride, setSubjectOverride] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  // Фильтруем кнопки по доступным шаблонам
  const availableButtons = PLAYBOOK_BUTTONS.filter(b => templateNames.includes(b.template));
  
  if (!hasEmail) return null;

  const handlePreview = async (templateName: string) => {
    setPreviewLoading(true);
    try {
      const result = await previewReply(companyId, templateName);
      setPreviewData(result);
      setSubjectOverride(result.subject);
    } catch (e: any) {
      toast.error(e?.message || 'Ошибка предпросмотра');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSend = async () => {
    if (!previewData) return;
    setSending(true);
    try {
      await sendReply(companyId, {
        template_name: previewData.template_name,
        subject_override: subjectOverride !== previewData.subject ? subjectOverride || undefined : undefined,
      });
      toast.success('Reply отправлен!');
      setPreviewData(null);
      setSubjectOverride(null);
      queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
    } catch (e: any) {
      toast.error(e?.message || 'Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const handleCancel = () => {
    setPreviewData(null);
    setSubjectOverride(null);
  };

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardHeader className="pb-2">
        <CardTitle 
          className="text-sm flex items-center gap-2 cursor-pointer select-none" 
          onClick={() => setExpanded(!expanded)}
        >
          <Reply className="h-4 w-4 text-primary" />
          Быстрый ответ
          <Badge variant="outline" className="text-[10px] px-1.5">
            {funnelStage === 'replied' ? 'Есть ответ' : funnelStage === 'email_opened' ? 'Открыто' : 'Email'}
          </Badge>
          {expanded ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
        </CardTitle>
      </CardHeader>
      
      {expanded && (
        <CardContent className="pt-0 space-y-3">
          {/* Превью перед отправкой */}
          {previewData ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs">
                <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-muted-foreground">Кому:</span>
                <span className="font-mono">{previewData.email_to}</span>
              </div>
              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase mb-1 block">Тема</label>
                <Textarea
                  value={subjectOverride || ''}
                  onChange={e => setSubjectOverride(e.target.value)}
                  className="min-h-[32px] text-sm py-1"
                  rows={1}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase mb-1 block">Тело письма</label>
                <div className="p-3 rounded-lg bg-muted/50 border text-sm max-h-[200px] overflow-y-auto whitespace-pre-wrap">
                  {previewData.body}
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  className="flex-1 bg-success hover:bg-success/90 text-success-foreground h-9"
                  onClick={handleSend}
                  disabled={sending}
                >
                  {sending ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Отправка...</>
                  ) : (
                    <><Send className="mr-2 h-4 w-4" /> Отправить</>
                  )}
                </Button>
                <Button variant="outline" size="icon" className="h-9 w-9" onClick={handleCancel}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Playbook кнопки */}
              <div className="flex flex-wrap gap-2">
                {availableButtons.map(btn => (
                  <Button
                    key={btn.template}
                    variant="outline"
                    size="sm"
                    className={cn("h-8 text-xs", btn.color)}
                    onClick={() => handlePreview(btn.template)}
                    disabled={previewLoading}
                  >
                    {previewLoading ? (
                      <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
                    ) : (
                      <btn.icon className="mr-1.5 h-3 w-3" />
                    )}
                    {btn.label}
                  </Button>
                ))}
                {availableButtons.length === 0 && (
                  <p className="text-xs text-muted-foreground italic">
                    Нет reply-шаблонов. Создайте шаблоны: reply_price, reply_examples, reply_deadline, reply_has_contractor, reply_rejection
                  </p>
                )}
              </div>
            </>
          )}
        </CardContent>
      )}
    </Card>
  );
}
