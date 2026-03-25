import { useState } from "react";
import ChatView from "./components/ChatView";
import FileBrowser from "./components/FileBrowser";
import Sidebar from "./components/Sidebar";
import { useSession } from "./hooks/useSession";
import { useWebSocket } from "./hooks/useWebSocket";
import "./styles/index.css";

export default function App() {
  const ws = useWebSocket();
  const session = useSession();

  const [enableDebug, setEnableDebug] = useState(true);
  const [showFileBrowser, setShowFileBrowser] = useState(false);

  return (
    <div className="app-layout">
      <Sidebar
        enableDebug={enableDebug}
        onToggleDebug={() => setEnableDebug((v) => !v)}
        showFileBrowser={showFileBrowser}
        onToggleFileBrowser={() => setShowFileBrowser((v) => !v)}
        pendingImages={session.pendingImages}
        uploadedPdfs={session.uploadedPdfs}
        onUploadDataset={session.uploadDataset}
        onUploadImages={session.uploadImages}
        onUploadPdfs={session.uploadPdfs}
        sessions={session.sessions}
        onFetchSessions={session.fetchSessions}
        onSave={session.saveSession}
        onLoad={session.loadSession}
        onExportHtml={session.exportHtml}
        hasMessages={ws.messages.length > 0}
      />

      <main className="main-area">
        <div className="top-bar">
          <h1 className="app-title">🧬 TissueAgent</h1>
          <div className="connection-status">
            <span
              className={`status-dot ${ws.isConnected ? "connected" : "disconnected"}`}
            />
            {ws.isConnected ? "Connected" : "Disconnected"}
          </div>
        </div>

        {ws.error && (
          <div className="error-banner">
            {ws.error}
            <button className="dismiss-btn" onClick={ws.clearError}>
              ✕
            </button>
          </div>
        )}

        <div className="content-area">
          {showFileBrowser && (
            <div className="file-browser-panel">
              <FileBrowser />
            </div>
          )}
          <div className={`chat-panel ${showFileBrowser ? "with-browser" : ""}`}>
            <ChatView
              messages={ws.messages}
              subagentStates={ws.subagentStates}
              isRunning={ws.isRunning}
              elapsed={ws.elapsed}
              enableDebug={enableDebug}
              onSendMessage={ws.sendMessage}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
