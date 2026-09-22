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
      <body className="min-h-full flex bg-zinc-50 text-zinc-900">
        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0">{children}</main>
      </body>
    </html>
  );
}
