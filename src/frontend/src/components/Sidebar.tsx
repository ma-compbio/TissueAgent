import type { FileInfo, SessionInfo } from "../types/messages";
import FileUpload from "./FileUpload";
import SessionManager from "./SessionManager";

interface Props {
  enableDebug: boolean;
  onToggleDebug: () => void;
  showFileBrowser: boolean;
  onToggleFileBrowser: () => void;
  pendingImages: FileInfo[];
  uploadedPdfs: FileInfo[];
  onUploadDataset: (files: FileList) => void;
  onUploadImages: (files: FileList) => void;
  onUploadPdfs: (files: FileList) => void;
  sessions: SessionInfo[];
  onFetchSessions: () => void;
  onSave: () => Promise<boolean>;
  onLoad: (filename: string) => Promise<boolean>;
  onExportHtml: () => void;
  hasMessages: boolean;
}

export default function Sidebar({
  enableDebug,
  onToggleDebug,
  showFileBrowser,
  onToggleFileBrowser,
  pendingImages,
  uploadedPdfs,
  onUploadDataset,
  onUploadImages,
  onUploadPdfs,
  sessions,
  onFetchSessions,
  onSave,
  onLoad,
  onExportHtml,
  hasMessages,
}: Props) {
  return (
    <aside className="sidebar">
      <FileUpload
        pendingImages={pendingImages}
        uploadedPdfs={uploadedPdfs}
        onUploadDataset={onUploadDataset}
        onUploadImages={onUploadImages}
        onUploadPdfs={onUploadPdfs}
      />

      <div className="upload-divider" />

      <div className="sidebar-controls">
        <button className="sidebar-btn" onClick={onToggleFileBrowser}>
          📁 {showFileBrowser ? "Close" : "Open"} File Browser
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
    </aside>
  );
}
