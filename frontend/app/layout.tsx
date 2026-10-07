import type { Metadata } from "next";
import "./globals.css";
import TopBar from "@/components/TopBar";

export const metadata: Metadata = {
  title: "開票小精靈",
  description: "把需求拷問成 Spec，再以自己的身份開 Azure DevOps 票",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant-TW">
      <body>
        <TopBar />
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
