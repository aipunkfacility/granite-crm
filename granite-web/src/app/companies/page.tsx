'use client';

import { Suspense } from "react";
import { CompaniesPageContent } from "./companies-content";

export default function CompaniesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Загрузка фильтров...</div>}>
      <CompaniesPageContent />
    </Suspense>
  );
}
