"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Per-tab memory for queries and results, so moving between pages keeps your work.
 *
 * Values live in a module-level map (survives client-side navigation) and are mirrored to
 * sessionStorage (survives a reload of the same tab, cleared when the tab closes). Storage can
 * be unavailable or full; every access is guarded and the in-memory copy still works.
 */
const PREFIX = "cellscope:";
const memory = new Map<string, unknown>();

export function readSession<T>(key: string): T | undefined {
  if (memory.has(key)) return memory.get(key) as T;
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.sessionStorage.getItem(PREFIX + key);
    if (raw === null) return undefined;
    const value = JSON.parse(raw) as T;
    memory.set(key, value);
    return value;
  } catch {
    return undefined;
  }
}

export function writeSession(key: string, value: unknown): void {
  memory.set(key, value);
  if (typeof window === "undefined") return;
  try {
    if (value === undefined || value === null) window.sessionStorage.removeItem(PREFIX + key);
    else window.sessionStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // Quota or privacy mode: the in-memory copy is enough for in-tab navigation.
  }
}

/**
 * useState that remembers its value for this tab. The first render uses only the in-memory copy
 * (empty during server rendering and hydration, so markup always matches); a stored value from
 * an earlier page load is applied right after mount.
 */
export function useSessionState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => (memory.has(key) ? (memory.get(key) as T) : initial));

  useEffect(() => {
    if (memory.has(key)) return;
    const stored = readSession<T>(key);
    if (stored !== undefined) setValue(stored);
    // Only on mount for this key.
  }, [key]);

  const update = useCallback(
    (next: T | ((previous: T) => T)) => {
      setValue((previous) => {
        const resolved = typeof next === "function" ? (next as (previous: T) => T)(previous) : next;
        writeSession(key, resolved);
        return resolved;
      });
    },
    [key],
  );

  return [value, update] as const;
}

/**
 * A choice that belongs to one result (selected row, open tab). It resets to `fallback` when a
 * different result is shown, and is remembered while the same result is on screen.
 */
export function useResultChoice<T>(key: string, stamp: string, fallback: T) {
  const [state, setState] = useSessionState<{ stamp: string; value: T } | null>(key, null);
  const value = state && state.stamp === stamp ? state.value : fallback;
  const set = useCallback((next: T) => setState({ stamp, value: next }), [setState, stamp]);
  return [value, set] as const;
}

/** Identifies one analysis result: the query and the parameters it ran with. */
export function resultStamp(response: { query_id: string; parameters?: Record<string, unknown> }): string {
  return `${response.query_id}|${JSON.stringify(response.parameters ?? {})}`;
}
