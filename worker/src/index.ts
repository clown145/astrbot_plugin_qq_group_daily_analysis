interface Env {
  REPORTS: KVNamespace;
  UPLOAD_TOKEN: string;
  PUBLIC_BASE_URL?: string;
  DEFAULT_TTL_SECONDS?: string;
}

type PublishPayload = {
  html?: unknown;
  platform_id?: unknown;
  group_id?: unknown;
  template?: unknown;
  ttl_seconds?: unknown;
  created_at?: unknown;
};

const HTML_KEY_PREFIX = "h:";
const META_KEY_PREFIX = "m:";
const DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60;
const MAX_HTML_BYTES = 24 * 1024 * 1024;
const REPORT_ID_PATTERN = /^[A-Za-z0-9_-]{20,40}$/;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/healthz") {
      return json({ ok: true, now: new Date().toISOString() });
    }

    if (request.method === "POST" && url.pathname === "/api/internal/reports") {
      return handlePublish(request, env);
    }

    if (request.method === "GET" && url.pathname.startsWith("/r/")) {
      const reportId = url.pathname.slice(3);
      return handleRender(reportId, env);
    }

    return new Response("Not Found", { status: 404 });
  },
};

async function handlePublish(request: Request, env: Env): Promise<Response> {
  if (!isAuthorized(request, env)) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  let payload: PublishPayload;
  try {
    payload = (await request.json()) as PublishPayload;
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  const html = typeof payload.html === "string" ? payload.html : "";
  if (!html.trim()) {
    return json({ ok: false, error: "html_required" }, 400);
  }

  if (new TextEncoder().encode(html).byteLength > MAX_HTML_BYTES) {
    return json({ ok: false, error: "html_too_large" }, 413);
  }

  const ttlSeconds = normalizeTtl(payload.ttl_seconds, env.DEFAULT_TTL_SECONDS);
  const reportId = generateReportId();
  const createdAt =
    typeof payload.created_at === "string" && payload.created_at
      ? payload.created_at
      : new Date().toISOString();
  const expiresAt = new Date(Date.now() + ttlSeconds * 1000).toISOString();

  const meta = {
    report_id: reportId,
    platform_id: asString(payload.platform_id),
    group_id: asString(payload.group_id),
    template: asString(payload.template),
    created_at: createdAt,
    expires_at: expiresAt,
  };

  await Promise.all([
    env.REPORTS.put(`${HTML_KEY_PREFIX}${reportId}`, html, {
      expirationTtl: ttlSeconds,
    }),
    env.REPORTS.put(`${META_KEY_PREFIX}${reportId}`, JSON.stringify(meta), {
      expirationTtl: ttlSeconds,
    }),
  ]);

  return json({
    ok: true,
    report_id: reportId,
    url: buildPublicUrl(request, env, reportId),
  });
}

async function handleRender(reportId: string, env: Env): Promise<Response> {
  if (!REPORT_ID_PATTERN.test(reportId)) {
    return notFound();
  }

  const html = await env.REPORTS.get(`${HTML_KEY_PREFIX}${reportId}`, "text");
  if (!html) {
    return notFound();
  }

  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
    },
  });
}

function isAuthorized(request: Request, env: Env): boolean {
  const expected = env.UPLOAD_TOKEN?.trim();
  if (!expected) {
    return false;
  }

  const header = request.headers.get("Authorization") || "";
  if (!header.startsWith("Bearer ")) {
    return false;
  }

  return header.slice(7).trim() === expected;
}

function generateReportId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function normalizeTtl(input: unknown, fallback?: string): number {
  const raw =
    typeof input === "number"
      ? input
      : typeof input === "string"
        ? Number.parseInt(input, 10)
        : fallback
          ? Number.parseInt(fallback, 10)
          : DEFAULT_TTL_SECONDS;

  if (!Number.isFinite(raw) || raw <= 0) {
    return DEFAULT_TTL_SECONDS;
  }

  return Math.min(Math.floor(raw), 365 * 24 * 60 * 60);
}

function buildPublicUrl(request: Request, env: Env, reportId: string): string {
  const configuredBase = env.PUBLIC_BASE_URL?.trim();
  const base = configuredBase || new URL(request.url).origin;
  return `${base.replace(/\/+$/g, "")}/r/${reportId}`;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function notFound(): Response {
  return new Response("Not Found", {
    status: 404,
    headers: {
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex, nofollow, noarchive",
    },
  });
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
