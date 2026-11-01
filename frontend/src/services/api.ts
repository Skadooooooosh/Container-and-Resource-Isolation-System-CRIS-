export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public detail?: any) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (res.status === 204) return undefined as T;

  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("json") ? await res.json() : await res.text();

  if (!res.ok) {
    const e = (body as any)?.error;
    const msg = e?.message ?? (typeof body === "string" ? body : JSON.stringify(body));
    const code = e?.code ?? `http_${res.status}`;
    throw new ApiError(code, msg, res.status, e?.detail);
  }

  return body as T;
}

export const post = <T = any>(p: string, b?: unknown) =>
  api<T>(p, { method: "POST", body: b === undefined ? undefined : JSON.stringify(b) });

export const patch = <T = any>(p: string, b?: unknown) =>
  api<T>(p, { method: "PATCH", body: b === undefined ? undefined : JSON.stringify(b) });

export const del = <T = any>(p: string) =>
  api<T>(p, { method: "DELETE" });
