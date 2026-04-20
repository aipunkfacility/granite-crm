import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import QueryProvider from "@/providers/query-provider";
import { Sidebar } from "@/components/layout/sidebar";
import { Toaster } from "@/components/ui/sonner"; // Заменили на Sonner

const inter = Inter({ subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  title: "Granite CRM",
  description: "Система управления базой клиентов",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className={inter.className}>
        <QueryProvider>
          <div className="flex h-screen overflow-hidden bg-background">
            <Sidebar />
            <main className="flex-1 overflow-y-auto overflow-x-hidden">
              <div className="container mx-auto py-6 px-4 md:px-8">
                {children}
              </div>
            </main>
          </div>
          <Toaster position="bottom-right" richColors /> {/* Настроили Sonner */}
        </QueryProvider>
      </body>
    </html>
  );
}
