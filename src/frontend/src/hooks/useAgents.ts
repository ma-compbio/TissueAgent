import { useEffect, useRef, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
}

/**
 * Fetches the specialist agent registry once on mount.
 *
 * Used by the copilot assignment-review UI to populate the per-step
 * "assigned agent" dropdown. The list is static for a given server
 * process so a single fetch is enough — no polling, no refresh.
 */
export function useAgents(): { agents: AgentInfo[]; loaded: boolean } {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loaded, setLoaded] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    fetch(`${API}/api/agents`)
      .then((r) => (r.ok ? (r.json() as Promise<AgentInfo[]>) : []))
      .then((data) => {
        if (!mountedRef.current) return;
        setAgents(data ?? []);
        setLoaded(true);
      })
      .catch(() => {
        if (!mountedRef.current) return;
        setLoaded(true); // mark loaded so UI doesn't spin forever
      });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return { agents, loaded };
}
