import type { FileInfo, SessionInfo } from "../types/messages";
import FileUpload from "./FileUpload";
import PlanViewer, { type PlanEntry } from "./PlanViewer";
import SessionManager from "./SessionManager";

interface Props {
  enableDebug: boolean;
  onToggleDebug: () => void;
  showFileBrowser: boolean;
  onToggleFileBrowser: () => void;
  uploadedFiles: FileInfo[];
  onUploadFiles: (files: FileList) => void;
  sessions: SessionInfo[];
  onFetchSessions: () => void;
  onSave: () => Promise<boolean>;
  onLoad: (filename: string) => Promise<boolean>;
  onExportHtml: () => void;
  hasMessages: boolean;
  planPrompt: string | null;
  planEntries: PlanEntry[];
  isRunning: boolean;
}

export default function Sidebar({
  enableDebug,
  onToggleDebug,
  showFileBrowser,
  onToggleFileBrowser,
  uploadedFiles,
  onUploadFiles,
  sessions,
  onFetchSessions,
  onSave,
  onLoad,
  onExportHtml,
  hasMessages,
  planPrompt,
  planEntries,
  isRunning,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <FileUpload
          uploadedFiles={uploadedFiles}
          onUploadFiles={onUploadFiles}
        />

        <div className="upload-divider" />

        <div className="sidebar-controls">
          <button className="sidebar-btn" onClick={onToggleFileBrowser}>
            {showFileBrowser ? "Close" : "Open"} File Browser
          </button>
          <label className="debug-toggle">
            <input
              type="checkbox"
              checked={enableDebug}
              onChange={onToggleDebug}
            />
            Enable Trace
          </label>
        </div>

        <div className="upload-divider" />

        <SessionManager
          sessions={sessions}
          onFetchSessions={onFetchSessions}
          onSave={onSave}
          onLoad={onLoad}
          onExportHtml={onExportHtml}
          hasMessages={hasMessages}
        />
      </div>

      <div className="sidebar-bottom">
        <PlanViewer
          prompt={planPrompt}
          entries={planEntries}
          isRunning={isRunning}
        />
      </div>
    </aside>
  );
}
