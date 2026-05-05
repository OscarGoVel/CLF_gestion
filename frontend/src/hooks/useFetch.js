import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/apiClient';

/**
 * Simple data-fetching hook.
 * @param {string|null} path  — API path; pass null to skip fetch
 * @param {any[]} deps        — re-fetch when these change (in addition to path)
 */
export function useFetch(path, deps = []) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError]   = useState(null);

  const fetch_ = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const d = await api.get(path);
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { data, loading, error, refetch: fetch_ };
}
