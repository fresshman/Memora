import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Memora · 离线私密对话复盘",
  description: "端侧离线私密对话智能复盘工具",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="flex min-h-full">
        <Sidebar />
        <main className="relative z-10 flex min-w-0 flex-1 flex-col">
          {children}
        </main>
      </body>
    </html>
  );
}
