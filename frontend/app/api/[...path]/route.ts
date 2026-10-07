// Proxies /api/* to the backend. BACKEND_URL is read at request time, so the same
// build works wherever the backend runs (a next.config rewrite would bake it in at build).

export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set(["connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding", "host"]);

function backendUrl(): string {
  return (process.env.BACKEND_URL || "http://localhost:8020").replace(/\/$/, "");
}

async function proxy(req: Request, { params }: { params: { path: string[] } }): Promise<Response> {
  const incoming = new URL(req.url);
  const target = `${backendUrl()}/api/${params.path.map(encodeURIComponent).join("/")}${incoming.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: `連不到小精靈後端（${backendUrl()}），請確認後端有在執行` },
      { status: 502 },
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase()) && key.toLowerCase() !== "set-cookie") out.set(key, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);

  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
