import { useCallback, useEffect, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export interface ModelOption {
  id: string;
  provider: "openai" | "anthropic";
  label: string;
}

export interface ModelSelection {
  orchestration: string;
  worker: string;
}

interface ListResponse {
  models: ModelOption[];
  selection: ModelSelection;
  default: string;
}

export function useModels() {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [selection, setSelection] = useState<ModelSelection | null>(null);
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

  return {
    models,
    selection,
    workerPinned,
    error,
    setOrchestration,
    setWorker,
    unpinWorker,
  };
}
