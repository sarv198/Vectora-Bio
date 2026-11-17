"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { readSession, writeSession } from "@/lib/session";

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

/** Requests still running for a persisted mutation, so a page reopened mid-run can wait for them. */
const inFlight = new Map<string, Promise<unknown>>();

/**
 * Run a request on demand (form submissions). With `persistKey`, the latest result is kept for
 * this browser tab, so leaving the page and coming back shows it again (see lib/session).
 */
export function useApiMutation<TRequest, TResponse>(
  runner: (request: TRequest) => Promise<TResponse>,
  persistKey?: string,
) {
  const [data, setData] = useState<TResponse | null>(() =>
    persistKey ? ((readSession<TResponse>(persistKey) ?? null) as TResponse | null) : null,
  );
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(() => (persistKey ? inFlight.has(persistKey) : false));
  const latest = useRef(0);

  // A run started before this page was left: show it as loading and pick up its result.
  useEffect(() => {
    if (!persistKey) return;
    if (data === null) {
      const stored = readSession<TResponse>(persistKey);
      if (stored) setData(stored);
    }
    const pending = inFlight.get(persistKey);
    if (!pending) return;
    let cancelled = false;
    setLoading(true);
    pending
      .then(() => {
        if (!cancelled) setData((readSession<TResponse>(persistKey) ?? null) as TResponse | null);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(toApiError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Mount only.
  }, [persistKey]);

  const run = useCallback(
    async (request: TRequest) => {
      const ticket = ++latest.current;
      setLoading(true);
      setError(null);
      const promise = runner(request);
      if (persistKey) {
        inFlight.set(persistKey, promise);
        // Stored even if the page is left before the response arrives.
        promise
          .then((result) => {
            if (inFlight.get(persistKey) === promise) writeSession(persistKey, result);
          })
          .catch(() => {
            if (inFlight.get(persistKey) === promise) writeSession(persistKey, null);
          })
          .finally(() => {
            if (inFlight.get(persistKey) === promise) inFlight.delete(persistKey);
          });
      }
      try {
        const result = await promise;
        if (ticket === latest.current) setData(result);
      } catch (err) {
        if (ticket === latest.current) {
          setData(null);
          setError(toApiError(err));
        }
      } finally {
        if (ticket === latest.current) setLoading(false);
      }
    },
    [runner, persistKey],
  );

  return { data, error, loading, run };
}
