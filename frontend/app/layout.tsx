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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Huninn&family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@500&display=swap"
        />
      </head>
      <body>
        <TopBar />
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
