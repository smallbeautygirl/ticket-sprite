"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Me } from "@/lib/api";
import Sprite from "@/components/Sprite";

export default function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [down, setDown] = useState<string | null>(null);

  useEffect(() => {
    if (pathname === "/login") return;
    api
      .me()
      .then((m) => {
        setMe(m);
        setDown(null);
      })
      .catch((err) => {
        setMe(null);
        if (err.status !== 401) setDown(err.message);
      });
  }, [pathname]);

  if (pathname === "/login") return null;

  return (
    <header className="topbar">
      <Link href="/" className="brand">
        <Sprite pose="logo" size={28} />
        開票小精靈
      </Link>
      <nav>
        <Link href="/" className={pathname === "/" || pathname.startsWith("/interviews") ? "on" : ""}>Interviews</Link>
        <Link href="/new" className={pathname === "/new" ? "on" : ""}>新增 Request</Link>
        <Link href="/settings" className={pathname === "/settings" ? "on" : ""}>設定</Link>
      </nav>
      {down && <span className="badge danger">{down}</span>}
      {me && (
        <>
          {(!me.ado.connected && !me.ado.dev_fallback) || me.ado.expired ? (
            <Link href="/settings" className="badge warn">尚未連結 Azure DevOps</Link>
          ) : me.ado.expiring_soon ? (
            <Link href="/settings" className="badge warn">PAT 即將到期</Link>
          ) : null}
          <span className="who">{me.display_name || me.email}</span>
          <button
            className="link"
            onClick={async () => {
              await api.logout();
              router.push("/login");
            }}
          >
            登出
          </button>
        </>
      )}
    </header>
  );
}
