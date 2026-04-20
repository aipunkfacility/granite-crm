'use client';

import { useCompanies } from "@/lib/hooks/use-companies";
import { CompanyTable } from "@/components/companies/company-table";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export default function CompaniesPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useCompanies({
    search: search || undefined,
    page: page,
    per_page: 50,
    order_by: 'crm_score',
    order_dir: 'desc'
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Компании</h1>
          <p className="text-slate-500">
            Управление базой потенциальных клиентов и стадиями воронки.
          </p>
        </div>
        
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Поиск по названию..."
            className="pl-10"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-[400px] w-full" />
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-destructive">
          <h2 className="text-lg font-semibold">Ошибка загрузки данных</h2>
          <p>{(error as Error).message}</p>
        </div>
      ) : (
        <>
          <CompanyTable companies={data?.items || []} />
          
          <div className="flex items-center justify-between text-sm text-slate-500 py-4">
            <div>
              Всего найдено: <span className="font-semibold">{data?.total || 0}</span>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded border bg-white px-3 py-1 hover:bg-slate-50 disabled:opacity-50"
              >
                Назад
              </button>
              <span className="font-medium">Страница {page}</span>
              <button 
                onClick={() => setPage(p => p + 1)}
                disabled={!data?.items || data.items.length < 50}
                className="rounded border bg-white px-3 py-1 hover:bg-slate-50 disabled:opacity-50"
              >
                Вперед
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
