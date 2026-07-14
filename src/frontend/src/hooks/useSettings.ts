import { useCallback, useEffect, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export interface AgentSettings {
  sandbox_enabled: boolean;
}

export function useSettings() {
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/settings`)
      .then((r) => (r.ok ? (r.json() as Promise<AgentSettings>) : Promise.reject(r)))
      .then((data) => {
        if (!cancelled) setSettings(data);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load settings");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setSandboxEnabled = useCallback(async (enabled: boolean) => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sandbox_enabled: enabled }),
      });
      if (!res.ok) throw new Error("Failed to save settings");
      const data: AgentSettings = await res.json();
      setSettings(data);
    } catch {
      setError("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }, []);

  return { settings, saving, error, setSandboxEnabled };
}
