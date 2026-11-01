export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}
export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch("/api" + path, { headers: { "Content-Type": "application/json" }, ...init });
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    const e = (body as any)?.error;
    throw new ApiError(e?.code ?? "http_error", e?.message ?? JSON.stringify((body as any)?.detail ?? body), res.status);
  }
  return body as T;
}
export const post = <T = any>(p: string, b?: unknown) => api<T>(p, { method: "POST", body: b === undefined ? undefined : JSON.stringify(b) });
