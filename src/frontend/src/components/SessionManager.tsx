import { useEffect, useState } from "react";
import type { SessionInfo } from "../types/messages";

interface Props {
  sessions: SessionInfo[];
  onFetchSessions: () => void;
  onSave: () => Promise<boolean>;
  onLoad: (filename: string) => Promise<boolean>;
  onExportHtml: () => void;
  hasMessages: boolean;
}

export default function SessionManager({
  sessions,
  onFetchSessions,
  onSave,
  onLoad,
  onExportHtml,
  hasMessages,
}: Props) {
  const [selected, setSelected] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    onFetchSessions();
  }, [onFetchSessions]);

  const handleSave = async () => {
    const ok = await onSave();
    setSaveStatus(ok ? "Session saved!" : "Failed to save.");
    setTimeout(() => setSaveStatus(null), 3000);
  };

  const handleLoad = async () => {
    if (!selected) return;
    const ok = await onLoad(selected);
    if (ok) window.location.reload(); // Reload to re-establish WS with new state
  };

  return (
    <div className="session-manager">
      <div className="session-label">Save or load chat sessions.</div>

      <button className="sidebar-btn" onClick={handleSave} disabled={!hasMessages}>
        💾 Save Current Session
      </button>
      {saveStatus && <div className="save-status">{saveStatus}</div>}

      <select
        className="session-select"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        <option value="">— Select a session —</option>
        {sessions.map((s) => (
          <option key={s.filename} value={s.filename}>
            {s.label}
          </option>
        ))}
      </select>

      <button
        className="sidebar-btn"
        onClick={handleLoad}
        disabled={!selected}
      >
        📂 Load Selected Session
      </button>

      {sessions.length === 0 && (
        <div className="no-files">No saved sessions yet.</div>
      )}

      {hasMessages && (
        <button className="sidebar-btn" onClick={onExportHtml}>
          ⬇ Download as HTML
        </button>
      )}
    </div>
  );
}
