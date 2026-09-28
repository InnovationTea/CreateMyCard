import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "DSL 渲染器",
  description: "极简 DSL 的本地 A2UI 渲染与预览",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="stylesheet" href="/fonts/harmonyos/harmonyos.css" />
      </head>
      <body>{children}</body>
    </html>
  );
}
