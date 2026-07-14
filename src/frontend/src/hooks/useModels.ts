import { useCallback, useEffect, useRef, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export type Provider = "openai" | "anthropic" | "openrouter";

export interface ModelOption {
  id: string;
  provider: Provider;
  label: string;
}

export interface ModelSelection {
  orchestration: string;
  worker: string;
}

export interface KeyStatus {
  env_var: string;
  env_set: boolean;
  ui_set: boolean;
  effective: boolean;
}

export type KeyStatusMap = Partial<Record<Provider, KeyStatus>>;

interface ListResponse {
  models: ModelOption[];
  selection: ModelSelection;
  default: string;
  keys: KeyStatusMap;
}

export function useModels() {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [selection, setSelection] = useState<ModelSelection | null>(null);
  const [keys, setKeys] = useState<KeyStatusMap>({});
  // Tracks whether the user has manually changed the worker model since
  // the last orchestration change. If false, orchestration changes also
  // update the worker so the two stay in sync by default.
  const [workerPinned, setWorkerPinned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const latestListReqRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    const token = ++latestListReqRef.current;
    fetch(`${API}/api/models/list`)
      .then((r) => (r.ok ? (r.json() as Promise<ListResponse>) : Promise.reject(r)))
      .then((data) => {
        if (!mountedRef.current || token !== latestListReqRef.current) return;
        setModels(data.models);
        setSelection(data.selection);
        setKeys(data.keys ?? {});
      })
      .catch(() => {
        if (mountedRef.current && token === latestListReqRef.current) {
          setError("Failed to load model list");
        }
      });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const persist = useCallback(async (next: ModelSelection) => {
    try {
      const res = await fetch(`${API}/api/models/set`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!res.ok) {
        if (mountedRef.current) setError("Failed to update model selection");
        return false;
      }
      if (mountedRef.current) setError(null);
      return true;
    } catch {
      if (mountedRef.current) setError("Failed to update model selection");
      return false;
    }
  }, []);

  const setOrchestration = useCallback(
    async (id: string) => {
      if (!selection) return;
      const prev = selection;
      const next: ModelSelection = workerPinned
        ? { orchestration: id, worker: selection.worker }
        : { orchestration: id, worker: id };
      setSelection(next);
      const ok = await persist(next);
      if (!ok && mountedRef.current) {
        // Revert the optimistic write when the server rejects it —
        // otherwise the UI keeps showing a selection that isn't persisted.
        setSelection(prev);
      }
    },
    [selection, workerPinned, persist],
  );

  const setWorker = useCallback(
    async (id: string) => {
      if (!selection) return;
      const prev = selection;
      const prevPinned = workerPinned;
      const next: ModelSelection = { orchestration: selection.orchestration, worker: id };
      setSelection(next);
      // Once the user touches the worker dropdown, stop auto-syncing.
      setWorkerPinned(true);
      const ok = await persist(next);
      if (!ok && mountedRef.current) {
        setSelection(prev);
        setWorkerPinned(prevPinned);
      }
    },
    [selection, workerPinned, persist],
  );

  const unpinWorker = useCallback(() => {
    if (!selection) return;
    setWorkerPinned(false);
    const next: ModelSelection = {
      orchestration: selection.orchestration,
      worker: selection.orchestration,
    };
    setSelection(next);
    persist(next);
  }, [selection, persist]);

  /**
   * Set or clear the in-memory API key for *provider*. Pass an empty
   * string to clear and fall back to the environment variable.
   */
  const setApiKey = useCallback(async (provider: Provider, key: string) => {
    const res = await fetch(`${API}/api/models/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, key }),
    });
    if (!res.ok) {
      setError("Failed to update API key");
      return false;
    }
    const data: { keys: KeyStatusMap } = await res.json();
    setKeys(data.keys);
    setError(null);
    return true;
  }, []);

  return {
    models,
    selection,
    workerPinned,
    keys,
    error,
    setOrchestration,
    setWorker,
    unpinWorker,
    setApiKey,
  };
}
