import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./styles.css";

export const metadata: Metadata = {
  title: "MIPI Admin — 采集审核工作台",
  description: "MIPI 本地采集、风险与人工审核工作台。",
};

export default function AdminLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
