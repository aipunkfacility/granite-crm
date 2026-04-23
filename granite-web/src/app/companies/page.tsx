'use client';

import { Suspense } from "react";
import { CompaniesPageContent } from "./companies-content";

export default function CompaniesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-400">Загрузка фильтров...</div>}>
      <CompaniesPageContent />
    </Suspense>
  );
}
