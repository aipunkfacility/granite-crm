'use client';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Company } from "@/lib/types/api";
import { FUNNEL_STAGES, SEGMENT_CONFIG } from "@/constants/funnel";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { ExternalLink, MessageCircle, Phone } from "lucide-react";

interface CompanyTableProps {
  companies: Company[];
  onSelectCompany?: (companyId: number) => void;
}

export function CompanyTable({ companies, onSelectCompany }: CompanyTableProps) {
  return (
    <div className="rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[300px]">Название</TableHead>
            <TableHead>Город</TableHead>
            <TableHead>Сегмент</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>Воронка</TableHead>
            <TableHead>Контакт</TableHead>
            <TableHead className="text-right">Последний контакт</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {companies.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                Компании не найдены
              </TableCell>
            </TableRow>
          ) : (
            companies.map((company) => {
              const stage = FUNNEL_STAGES[company.funnel_stage];
              const segment = company.segment ? SEGMENT_CONFIG[company.segment] : null;

              return (
                /* V-01: клик по строке → открывает Sheet */
                <TableRow
                  key={company.id}
                  className="group hover:bg-muted/50 cursor-pointer"
                  onClick={() => onSelectCompany?.(company.id)}
                >
                  <TableCell className="font-medium">
                    <span className="text-primary hover:underline">
                      {company.name}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{company.city}</TableCell>
                  <TableCell>
                    {segment && (
                      <Badge variant={segment.variant}>
                        {segment.label}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {/* V-10: font-mono-code (13px JetBrains Mono) */}
                    <span className="font-mono-code font-medium text-foreground">
                      {company.crm_score}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={stage.variant} className="whitespace-nowrap">
                      {stage.label}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {company.telegram && (
                        <a
                          href={`https://t.me/${company.telegram.replace('@', '')}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-info hover:scale-110 transition-transform"
                          /* Клик по ссылке НЕ открывает Sheet */
                          onClick={e => e.stopPropagation()}
                        >
                          <MessageCircle className="h-4 w-4" />
                        </a>
                      )}
                      {company.phones.length > 0 && (
                        <a
                          href={`tel:${company.phones[0]}`}
                          className="text-muted-foreground hover:text-foreground"
                          onClick={e => e.stopPropagation()}
                        >
                          <Phone className="h-4 w-4" />
                        </a>
                      )}
                      {company.website && (
                        <a
                          href={company.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-muted-foreground hover:text-foreground"
                          onClick={e => e.stopPropagation()}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {company.last_contact_at
                      ? formatDistanceToNow(new Date(company.last_contact_at), { addSuffix: true, locale: ru })
                      : '—'}
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
