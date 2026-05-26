import { useEffect, useState } from "react";
import type { SessionInfo } from "../types/messages";

interface Props {
  sessions: SessionInfo[];
  onFetchSessions: () => void;
  /** Returns ``true`` on success, or an error detail string on failure. */
  onSave: () => Promise<true | string>;
  onLoad: (filename: string) => Promise<boolean>;
  /** Returns ``true`` on success, or an error detail string on failure. */
  onClear: () => Promise<true | string>;
  /** Returns ``true`` on success, or an error detail string on failure. */
  onDelete: (filename: string) => Promise<true | string>;
  onExportHtml: () => void;
  onExportMarkdown: () => void;
  hasMessages: boolean;
}

export default function SessionManager({
  sessions,
  onFetchSessions,
  onSave,
  onLoad,
  onClear,
  onDelete,
  onExportHtml,
  onExportMarkdown,
  hasMessages,
}: Props) {
  const [selected, setSelected] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | null>(null);

  useEffect(() => {
    onFetchSessions();
  }, [onFetchSessions]);

  const showStatus = (msg: string, ms = 3000) => {
    setLoadStatus(msg);
    setTimeout(() => setLoadStatus(null), ms);
  };

  const handleSave = async () => {
    const result = await onSave();
    setSaveStatus(result === true ? "Session saved!" : result);
    setTimeout(() => setSaveStatus(null), 4000);
  };

  const handleClear = async () => {
    const ok = window.confirm(
      "Clear the current session?\n\n" +
        "This wipes the chat, sub-agent traces, and plan. " +
        "Saved sessions on disk are not affected.",
    );
    if (!ok) return;
    const result = await onClear();
    setSaveStatus(result === true ? "Session cleared." : result);
    setTimeout(() => setSaveStatus(null), 4000);
  };

  const handleLoad = async () => {
    if (!selected) return;
    const ok = await onLoad(selected);
    showStatus(ok ? "Session loaded." : "Failed to load.");
  };

  const handleDelete = async () => {
    if (!selected) return;
    const target = sessions.find((s) => s.filename === selected);
    const label = target?.title || target?.label || selected;
    const ok = window.confirm(`Delete saved session?\n\n${label}`);
    if (!ok) return;
    const result = await onDelete(selected);
    if (result === true) {
      setSelected(""); // session is gone; clear the dropdown
      showStatus("Session deleted.");
    } else {
      showStatus(result, 4000);
    }
  };

  return (
    <div className="session-manager">
      <div className="session-label">Save or load chat sessions.</div>

      <div className="session-row-actions">
        <button
          className="sidebar-btn"
          onClick={handleSave}
          disabled={!hasMessages}
          title={
            hasMessages
              ? "Save the current chat, plan, and prompts snapshot"
              : "Nothing to save yet"
          }
        >
          💾 Save
        </button>
        <button
          className="sidebar-btn session-btn-danger"
          onClick={handleClear}
          disabled={!hasMessages}
          title={
            hasMessages
              ? "Wipe the current chat, traces, and plan"
              : "Nothing to clear"
          }
        >
          🧹 Clear
        </button>
      </div>
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

      <div className="session-row-actions">
        <button
          className="sidebar-btn"
          onClick={handleLoad}
          disabled={!selected}
        >
          📂 Load
        </button>
        <button
          className="sidebar-btn session-btn-danger"
          onClick={handleDelete}
          disabled={!selected}
          title="Delete the selected saved session"
        >
          🗑 Delete
        </button>
      </div>
      {loadStatus && <div className="save-status">{loadStatus}</div>}

      {sessions.length === 0 && (
        <div className="no-files">No saved sessions yet.</div>
      )}

      {hasMessages && (
        <div className="session-export-actions">
          <button className="sidebar-btn" onClick={onExportHtml}>
            ⬇ HTML
          </button>
          <button className="sidebar-btn" onClick={onExportMarkdown}>
            ⬇ Markdown
          </button>
        </div>
      )}
    </div>
  );
}
