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
import Link from "next/link";
import { ExternalLink, MessageCircle, Phone } from "lucide-react";

interface CompanyTableProps {
  companies: Company[];
}

export function CompanyTable({ companies }: CompanyTableProps) {
  return (
    <div className="rounded-md border bg-white">
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
                <TableRow key={company.id} className="group hover:bg-slate-50">
                  <TableCell className="font-medium">
                    <Link 
                      href={`/companies/${company.id}`}
                      className="text-indigo-600 hover:underline"
                    >
                      {company.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-slate-500">{company.city}</TableCell>
                  <TableCell>
                    {segment && (
                      <Badge variant={segment.variant}>
                        {segment.label}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="font-mono font-bold text-slate-700">
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
                        <a href={`https://t.me/${company.telegram.replace('@', '')}`} target="_blank" rel="noreferrer" className="text-sky-500 hover:scale-110 transition-transform">
                          <MessageCircle className="h-4 w-4" />
                        </a>
                      )}
                      {company.phones.length > 0 && (
                        <a href={`tel:${company.phones[0]}`} className="text-slate-400 hover:text-slate-600">
                          <Phone className="h-4 w-4" />
                        </a>
                      )}
                      {company.website && (
                        <a href={company.website} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-slate-600">
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-xs text-slate-400">
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
