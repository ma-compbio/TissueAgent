import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Hook that owns a numeric layout dimension (e.g. sidebar width) with:
 *   - localStorage persistence so resize survives page reloads,
 *   - clamping to a min/max range,
 *   - throttled write-back (avoid hammering storage during a drag).
 *
 * Returns ``[value, applyDelta, set]``. ``applyDelta`` is the function
 * to pass into ``<Splitter onResize=...>``; ``set`` is for programmatic
 * updates (e.g. a "reset to default" action you might add later).
 */
export function usePersistedSize(
  storageKey: string,
  defaultValue: number,
  min: number,
  max: number,
): [number, (delta: number) => void, (next: number) => void] {
  const clamp = useCallback(
    (n: number) => Math.min(max, Math.max(min, n)),
    [min, max],
  );

  // Hydrate from localStorage on first render. On the server side this
  // would have no localStorage, but Vite is client-only so we can just
  // touch it directly.
  const [value, setValueState] = useState<number>(() => {
    if (typeof window === "undefined") return defaultValue;
    const raw = window.localStorage.getItem(storageKey);
    if (raw === null) return defaultValue;
    const parsed = Number.parseFloat(raw);
    if (!Number.isFinite(parsed)) return defaultValue;
    return clamp(parsed);
  });

  // Throttle persistence to one write per animation frame; otherwise a
  // 500ms drag generates ~30 storage writes.
  const pendingWriteRef = useRef<number | null>(null);
  const persist = useCallback(
    (n: number) => {
      if (typeof window === "undefined") return;
      if (pendingWriteRef.current !== null) {
        cancelAnimationFrame(pendingWriteRef.current);
      }
      pendingWriteRef.current = requestAnimationFrame(() => {
        try {
          window.localStorage.setItem(storageKey, String(n));
        } catch {
          // Storage might be unavailable (private mode, quota); ignore.
        }
        pendingWriteRef.current = null;
      });
    },
    [storageKey],
  );

  const set = useCallback(
    (next: number) => {
      const clamped = clamp(next);
      setValueState(clamped);
      persist(clamped);
    },
    [clamp, persist],
  );

  const applyDelta = useCallback(
    (delta: number) => {
      setValueState((prev) => {
        const next = clamp(prev + delta);
        if (next === prev) return prev;
        persist(next);
        return next;
      });
    },
    [clamp, persist],
  );

  // Ensure pending write is flushed on unmount.
  useEffect(() => {
    return () => {
      if (pendingWriteRef.current !== null) {
        cancelAnimationFrame(pendingWriteRef.current);
      }
    };
  }, []);

  return [value, applyDelta, set];
}
