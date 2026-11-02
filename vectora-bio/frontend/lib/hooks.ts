"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";

function toApiError(error: unknown): ApiError {
  return error instanceof ApiError ? error : new ApiError(0, "client_error", String(error));
}

/** Fetch on mount and whenever `deps` change. */
export function useApiQuery<T>(fetcher: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setData(null);
          setError(toApiError(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // `deps` is the caller's dependency list; the fetcher itself is read from a ref.
  }, [...deps, version]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return { data, error, loading, reload };
}

/** Run a request on demand (form submissions). */
export function useApiMutation<TRequest, TResponse>(runner: (request: TRequest) => Promise<TResponse>) {
  const [data, setData] = useState<TResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(
    async (request: TRequest) => {
      setLoading(true);
      setError(null);
      try {
        setData(await runner(request));
      } catch (err) {
        setData(null);
        setError(toApiError(err));
      } finally {
        setLoading(false);
      }
    },
    [runner],
  );

  return { data, error, loading, run };
}
