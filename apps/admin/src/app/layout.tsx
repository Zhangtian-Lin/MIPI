import type { ReactNode } from "react";
import "./styles.css";

export default function AdminLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}

