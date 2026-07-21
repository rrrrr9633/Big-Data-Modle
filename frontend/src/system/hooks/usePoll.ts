import { useEffect, useRef, useState } from 'react';

interface PollResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => void;
}

/**
 * Polls `fetcher` every `intervalMs`. Falls through silently if backend
 * is unavailable — consumers handle the null data with mock fallback.
 */
export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
): PollResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const counterRef = useRef(0);

  const run = async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!enabled) return;
    run();
    const id = setInterval(run, intervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, enabled]);

  return { data, error, loading, refresh: () => { counterRef.current++; run(); } };
}