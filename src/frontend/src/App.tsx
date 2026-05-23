import { useEffect, useState } from "react";
import ChatView from "./components/ChatView";
import FileBrowser from "./components/FileBrowser";
import Sidebar from "./components/Sidebar";
import ThemeToggle from "./components/ThemeToggle";
import { useModels } from "./hooks/useModels";
import { usePlan } from "./hooks/usePlan";
import type { PlanPayload } from "./hooks/usePlan";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";
import { useWebSocket } from "./hooks/useWebSocket";
import "./styles/index.css";

export default function App() {
  const ws = useWebSocket();
  const session = useSession();
  const modelHook = useModels();
  const planHook = usePlan();
  const { theme, toggleTheme } = useTheme();

  const [enableDebug, setEnableDebug] = useState(false);
  const [showFileBrowser, setShowFileBrowser] = useState(false);

  // Forward WebSocket plan_updated events into the plan store.
  useEffect(() => {
    if (ws.planEvent) {
      planHook.applyEvent(ws.planEvent as PlanPayload);
    }
  }, [ws.planEvent, planHook]);

  return (
    <div className="app-layout">
      <Sidebar
        enableDebug={enableDebug}
        onToggleDebug={() => setEnableDebug((v) => !v)}
        showFileBrowser={showFileBrowser}
        onToggleFileBrowser={() => setShowFileBrowser((v) => !v)}
        uploadedFiles={session.uploadedFiles}
        onUploadFiles={session.uploadFiles}
        sessions={session.sessions}
        onFetchSessions={session.fetchSessions}
        onSave={session.saveSession}
        onLoad={session.loadSession}
        onExportHtml={session.exportHtml}
        hasMessages={ws.messages.length > 0}
        plan={planHook.plan}
        planMarkdown={planHook.markdown}
        isRunning={ws.isRunning}
        mode={ws.mode}
        onChangeMode={ws.setMode}
        models={modelHook.models}
        modelSelection={modelHook.selection}
        workerPinned={modelHook.workerPinned}
        onChangeOrchestrationModel={modelHook.setOrchestration}
        onChangeWorkerModel={modelHook.setWorker}
        onResetWorkerModel={modelHook.unpinWorker}
        modelKeys={modelHook.keys}
        onSaveApiKey={modelHook.setApiKey}
      />

      <main className="main-area">
        <div className="top-bar">
          <div className="app-brand">
            <img
              src="/tissueagent-icon.png"
              alt=""
              aria-hidden="true"
              className="app-logo"
            />
            <h1 className="app-title">TissueAgent</h1>
          </div>
          <div className="top-bar-right">
            <div className="connection-status">
              <span
                className={`status-dot ${ws.isConnected ? "connected" : "disconnected"}`}
              />
              {ws.isConnected ? "Connected" : "Disconnected"}
            </div>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
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
          <div className="chat-panel">
            <ChatView
              messages={ws.messages}
              subagentStates={ws.subagentStates}
              liveTraces={ws.liveTraces}
              isRunning={ws.isRunning}
              elapsed={ws.elapsed}
              enableDebug={enableDebug}
              onSendMessage={ws.sendMessage}
            />
          </div>
        </div>
      </main>

      {showFileBrowser && (
        <div className="modal-overlay" onClick={() => setShowFileBrowser(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>File Browser</h3>
              <button
                className="modal-close-btn"
                onClick={() => setShowFileBrowser(false)}
              >
                ✕
              </button>
            </div>
            <FileBrowser />
          </div>
        </div>
      )}
    </div>
  );
}
