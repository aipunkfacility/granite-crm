import { FunnelStage, Segment } from "@/lib/types/api";

export const FUNNEL_STAGES: Record<FunnelStage, { label: string; color: string; variant: "outline" | "default" | "secondary" | "destructive" }> = {
  new: { label: "Новый", color: "slate", variant: "outline" },
  email_sent: { label: "Письмо отправлено", color: "blue", variant: "default" },
  email_opened: { label: "Письмо открыто", color: "indigo", variant: "default" },
  tg_sent: { label: "Написали в TG", color: "violet", variant: "default" },
  wa_sent: { label: "Написали в WA", color: "green", variant: "default" },
  replied: { label: "Ответили", color: "emerald", variant: "secondary" },
  interested: { label: "Заинтересованы", color: "teal", variant: "secondary" },
  not_interested: { label: "Не интересно", color: "orange", variant: "outline" },
  unreachable: { label: "Недоступен", color: "red", variant: "destructive" },
};

export const SEGMENT_CONFIG: Record<Segment, { label: string; variant: "default" | "secondary" | "outline" | "destructive" }> = {
  A: { label: "A", variant: "default" },
  B: { label: "B", variant: "secondary" },
  C: { label: "C", variant: "outline" },
  D: { label: "D", variant: "outline" },
  spam: { label: "Spam", variant: "destructive" },
};
