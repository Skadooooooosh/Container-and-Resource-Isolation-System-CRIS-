import { useCallback, useEffect, useState } from "react";
export function usePoll<T>(fn: () => Promise<T>, ms: number | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const run = useCallback(async () => {
    try { setData(await fn()); setError(null); } catch (e: any) { setError(e.message ?? String(e)); } finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); if (ms) { const t = setInterval(run, ms); return () => clearInterval(t); } }, [run, ms]);
  return { data, error, loading, reload: run };
}
export const Err = ({ msg }: { msg: string | null }) => (msg ? <div className="err" role="alert">{msg}</div> : null);
export const fmtBytes = (n?: number | null) => (n == null ? "—" : n > 1048576 ? (n / 1048576).toFixed(1) + " MiB" : (n / 1024).toFixed(0) + " KiB");
