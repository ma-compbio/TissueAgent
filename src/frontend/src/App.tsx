import { useCallback, useEffect, useState } from "react";
import ChatView from "./components/ChatView";
import ContactPage from "./components/ContactPage";
import FileBrowser from "./components/FileBrowser";
import Sidebar from "./components/Sidebar";
import ThemeToggle from "./components/ThemeToggle";
import TopNav from "./components/TopNav";
import TutorialPage from "./components/TutorialPage";
import { useAgents } from "./hooks/useAgents";
import { useModels } from "./hooks/useModels";
import { usePlan } from "./hooks/usePlan";
import type { PlanPayload } from "./hooks/usePlan";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";
import { useWebSocket } from "./hooks/useWebSocket";
import "./styles/index.css";

/** Three top-level views. The chat page keeps the sidebar; tutorial
 *  and contact are single-column reference pages. */
export type Page = "chat" | "tutorial" | "contact";

const PAGES: readonly Page[] = ["chat", "tutorial", "contact"] as const;

function _readPageFromUrl(): Page {
  if (typeof window === "undefined") return "chat";
  const raw = new URLSearchParams(window.location.search).get("page");
  return PAGES.includes(raw as Page) ? (raw as Page) : "chat";
}

export default function App() {
  const ws = useWebSocket();
  const session = useSession();
  const modelHook = useModels();
  const planHook = usePlan();
  const agentsHook = useAgents();
  const { theme, toggleTheme } = useTheme();

  const [enableDebug, setEnableDebug] = useState(false);
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [page, setPage] = useState<Page>(_readPageFromUrl);

  // Sync ?page=... in the URL so reloads + bookmarks land on the right view.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const current = url.searchParams.get("page");
    if (page === "chat") {
      if (current !== null) {
        url.searchParams.delete("page");
        window.history.replaceState({}, "", url.toString());
      }
    } else if (current !== page) {
      url.searchParams.set("page", page);
      window.history.replaceState({}, "", url.toString());
    }
  }, [page]);

  // Honor back/forward navigation in the browser.
  useEffect(() => {
    const onPop = () => setPage(_readPageFromUrl());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Forward WebSocket plan_updated events into the plan store.
  useEffect(() => {
    if (ws.planEvent) {
      planHook.applyEvent(ws.planEvent as PlanPayload);
    }
  }, [ws.planEvent, planHook]);

  // Composite load: hit the load endpoint, then refresh the frontend in
  // place — reconnect the WS so the server re-sends history + mode, and
  // refetch the plan from REST. Replaces the old ``window.location.reload``
  // so users keep their open file browser, scroll position, etc.
  const handleLoadSession = useCallback(
    async (filename: string) => {
      const ok = await session.loadSession(filename);
      if (!ok) return false;
      ws.reconnect();
      await planHook.refresh();
      return true;
    },
    [session, ws, planHook],
  );

  // Tutorial and Contact: single-column doc layout, no sidebar.
  if (page === "tutorial" || page === "contact") {
    return (
      <div className="app-layout app-layout-doc">
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
            <TopNav current={page} onNavigate={setPage} />
            <div className="top-bar-right">
              <ThemeToggle theme={theme} onToggle={toggleTheme} />
            </div>
          </div>
          <div className="content-area-doc">
            {page === "tutorial" ? <TutorialPage /> : <ContactPage />}
          </div>
        </main>
      </div>
    );
  }

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
        onLoad={handleLoadSession}
        onDelete={session.deleteSession}
        onExportHtml={session.exportHtml}
        onExportMarkdown={session.exportMarkdown}
        hasMessages={ws.messages.length > 0}
        plan={planHook.plan}
        planMarkdown={planHook.markdown}
        isRunning={ws.isRunning}
        mode={ws.mode}
        onChangeMode={ws.setMode}
        reviewState={ws.reviewState}
        pipelineStage={ws.pipelineStage}
        agents={agentsHook.agents}
        onApprovePlan={ws.approvePlan}
        onEditPlan={ws.editPlan}
        onPlanFeedback={ws.sendPlanFeedback}
        onApproveAssignments={ws.approveAssignments}
        onEditAssignments={ws.editAssignments}
        onAssignmentsFeedback={ws.sendAssignmentsFeedback}
        onCancelRun={ws.cancelRun}
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
          <TopNav current={page} onNavigate={setPage} />
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
