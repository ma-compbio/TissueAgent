import { useCallback, useEffect, useState } from "react";

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

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/models/list`)
      .then((r) => (r.ok ? (r.json() as Promise<ListResponse>) : Promise.reject(r)))
      .then((data) => {
        if (cancelled) return;
        setModels(data.models);
        setSelection(data.selection);
        setKeys(data.keys ?? {});
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load model list");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback(async (next: ModelSelection) => {
    const res = await fetch(`${API}/api/models/set`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
    if (!res.ok) {
      setError("Failed to update model selection");
      return false;
    }
    setError(null);
    return true;
  }, []);

  const setOrchestration = useCallback(
    async (id: string) => {
      if (!selection) return;
      const next: ModelSelection = workerPinned
        ? { orchestration: id, worker: selection.worker }
        : { orchestration: id, worker: id };
      setSelection(next);
      await persist(next);
    },
    [selection, workerPinned, persist],
  );

  const setWorker = useCallback(
    async (id: string) => {
      if (!selection) return;
      const next: ModelSelection = { orchestration: selection.orchestration, worker: id };
      setSelection(next);
      // Once the user touches the worker dropdown, stop auto-syncing.
      setWorkerPinned(true);
      await persist(next);
    },
    [selection, persist],
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
