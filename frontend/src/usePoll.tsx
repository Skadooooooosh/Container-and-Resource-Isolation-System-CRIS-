import { useCallback, useEffect, useRef, useState } from "react";

export function usePoll<T>(
  fn: () => Promise<T>,
  ms: number | null,
  deps: unknown[] = [],
  enabled: boolean = true
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const inFlightRef = useRef(false);
  const unmountedRef = useRef(false);
  const seqRef = useRef(0);

  const run = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    const currentSeq = ++seqRef.current;

    try {
      const res = await fn();
      if (!unmountedRef.current && currentSeq === seqRef.current) {
        setData(res);
        setError(null);
      }
    } catch (e: any) {
      if (!unmountedRef.current && currentSeq === seqRef.current) {
        setError(e?.message ?? String(e));
      }
    } finally {
      inFlightRef.current = false;
      if (!unmountedRef.current && currentSeq === seqRef.current) {
        setLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    unmountedRef.current = false;
    if (!enabled) return;

    run();

    if (ms) {
      const timer = setInterval(() => {
        if (!inFlightRef.current && enabled) {
          run();
        }
      }, ms);
      return () => {
        clearInterval(timer);
        unmountedRef.current = true;
      };
    }

    return () => {
      unmountedRef.current = true;
    };
  }, [run, ms, enabled]);

  return { data, error, loading, reload: run };
}

export const Err = ({ msg, onDismiss }: { msg: string | null; onDismiss?: () => void }) =>
  msg ? (
    <div className="alert alert-error" role="alert">
      <span className="alert-icon">⚠</span>
      <div className="alert-content">{msg}</div>
      {onDismiss && (
        <button className="alert-close" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  ) : null;

export const fmtBytes = (n?: number | null) => {
  if (n == null) return "—";
  if (n >= 1073741824) return (n / 1073741824).toFixed(2) + " GiB";
  if (n >= 1048576) return (n / 1048576).toFixed(1) + " MiB";
  if (n >= 1024) return (n / 1024).toFixed(0) + " KiB";
  return n + " B";
};
