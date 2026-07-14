import { useCallback, useEffect, useMemo, useState } from "react";
import ChatView from "./components/ChatView";
import ContactPage from "./components/ContactPage";
import MetricsPage from "./components/MetricsPage";
import PlanColumn from "./components/PlanColumn";
import Sidebar from "./components/Sidebar";
import Splitter from "./components/Splitter";
import ThemeToggle from "./components/ThemeToggle";
import {
  BackToChatButton,
  ContactButton,
  MetricsButton,
  SettingsButton,
  TutorialButton,
} from "./components/TopNav";
import SettingsPage from "./components/SettingsPage";
import TutorialPage from "./components/TutorialPage";
import { useAgents } from "./hooks/useAgents";
import { useModels } from "./hooks/useModels";
import { usePersistedSize } from "./hooks/usePersistedSize";
import { usePlan } from "./hooks/usePlan";
import type { PlanPayload } from "./hooks/usePlan";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";
import { useWebSocket } from "./hooks/useWebSocket";
import "./styles/index.css";

// Sidebar width — below ~240 the Projects + Files stack gets cramped;
// above ~600 the chat area shrinks too much on smaller laptops.
const SIDEBAR_WIDTH_KEY = "tissueagent:sidebar-width";
const SIDEBAR_WIDTH_DEFAULT = 320;
const SIDEBAR_WIDTH_MIN = 240;
const SIDEBAR_WIDTH_MAX = 600;

// Plan column on the right of the chat. The plan needs enough room to
// render markdown comfortably; below ~260 it wraps awkwardly.
const PLAN_COL_WIDTH_KEY = "tissueagent:plan-col-width";
const PLAN_COL_WIDTH_DEFAULT = 360;
const PLAN_COL_WIDTH_MIN = 260;
const PLAN_COL_WIDTH_MAX = 720;

/** Top-level views. Chat keeps the sidebar; settings, tutorial, contact,
 *  and metrics are single-column reference pages. */
export type Page = "chat" | "settings" | "tutorial" | "contact" | "metrics";

const PAGES: readonly Page[] = [
  "chat",
  "settings",
  "tutorial",
  "contact",
  "metrics",
] as const;

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

  const [page, setPage] = useState<Page>(_readPageFromUrl);
  const [sidebarWidth, resizeSidebar] = usePersistedSize(
    SIDEBAR_WIDTH_KEY,
    SIDEBAR_WIDTH_DEFAULT,
    SIDEBAR_WIDTH_MIN,
    SIDEBAR_WIDTH_MAX,
  );
  const [planColWidth, resizePlanCol] = usePersistedSize(
    PLAN_COL_WIDTH_KEY,
    PLAN_COL_WIDTH_DEFAULT,
    PLAN_COL_WIDTH_MIN,
    PLAN_COL_WIDTH_MAX,
  );
  const [fileBrowserRefreshKey, setFileBrowserRefreshKey] = useState(0);

  const handleUploadToLibrary = useCallback(
    async (files: FileList) => {
      await session.uploadFiles(files, "library");
      setFileBrowserRefreshKey((k) => k + 1);
    },
    [session],
  );

  // ChatGPT-style "+" button next to the chat input. Same target as
  // the standalone sidebar uploads used to be: per-project ``uploads/``.
  const handleUploadToProject = useCallback(
    async (files: FileList) => {
      await session.uploadFiles(files, "project");
      setFileBrowserRefreshKey((k) => k + 1);
    },
    [session],
  );

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
    // Depend only on the event + the stable applyEvent callback. usePlan
    // returns a fresh object each render, so depending on the whole
    // `planHook` re-fires this effect every render (and applyEvent sets
    // state, so that would loop). applyEvent is a stable useCallback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.planEvent, planHook.applyEvent]);

  // Auto-save fires server-side on every prompt / pause / completion.
  // The frontend uses each project_saved event as a cue to refetch the
  // project list and re-bind the active project id.
  //
  // IMPORTANT: depend on the individual stable callbacks, NOT the whole
  // `session` object — useSession() returns a new object every render,
  // which would re-trigger this effect in an infinite loop.
  const { setCurrentProjectId, fetchSessions } = session;
  useEffect(() => {
    if (!ws.projectSavedEvent) return;
    setCurrentProjectId(ws.projectSavedEvent.project_id);
    fetchSessions();
    // Project-side files (uploads/, outputs/) may have changed too —
    // bump the refresh key so the sidebar Files panel re-fetches
    // without the user having to click refresh.
    setFileBrowserRefreshKey((k) => k + 1);
    // Depend only on the event, NOT the whole `session` object. useSession
    // returns a fresh object literal every render, so including `session`
    // here re-fires this effect on each render — and since it calls
    // setState, that's an infinite re-fetch loop. The session callbacks it
    // uses (setCurrentProjectId / fetchSessions) are stable across renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.projectSavedEvent]);

  // On first mount, load the saved-project list AND recover the active
  // project id, so the sidebar shows past projects immediately on
  // startup/refresh — not only after the first run's project_saved event.
  useEffect(() => {
    session.fetchSessions();
    session.fetchCurrentProject();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      await session.fetchCurrentProject();
      setFileBrowserRefreshKey((k) => k + 1);
      return true;
    },
    [session, ws, planHook],
  );

  // Composite clear (used by the projects-panel "+" button): wipe
  // server state, then refresh in place.
  const handleClearSession = useCallback(async () => {
    const result = await session.clearSession();
    if (result !== true) return result;
    ws.reconnect();
    await planHook.refresh();
    // Refresh the project list so the just-parked conversation shows up as a
    // standalone project (the server parked it on clear).
    await session.fetchSessions();
    setFileBrowserRefreshKey((k) => k + 1);
    return true;
  }, [session, ws, planHook]);

  const currentProjectTitle = useMemo(() => {
    if (!session.currentProjectId) return "";
    return (
      session.sessions.find(
        (s) => (s.project_id ?? s.filename) === session.currentProjectId,
      )?.title ?? ""
    );
  }, [session.currentProjectId, session.sessions]);

  // Settings, Tutorial, Contact, Metrics: single-column doc layout, no sidebar.
  if (
    page === "settings" ||
    page === "tutorial" ||
    page === "contact" ||
    page === "metrics"
  ) {
    return (
      <div className="app-layout app-layout-doc">
        <main className="main-area">
          <div className="top-bar">
            <button
              type="button"
              className="app-brand app-brand-button"
              onClick={() => setPage("chat")}
              aria-label="Return to chat"
              title="Return to chat"
            >
              <img
                src="/tissueagent-icon.png"
                alt=""
                aria-hidden="true"
                className="app-logo"
              />
              <h1 className="app-title">TissueAgent</h1>
            </button>
            <div className="top-bar-right">
              <BackToChatButton onClick={() => setPage("chat")} />
              <span className="top-bar-divider" aria-hidden="true" />
              <MetricsButton
                active={page === "metrics"}
                onClick={() => setPage("metrics")}
              />
              <TutorialButton
                active={page === "tutorial"}
                onClick={() => setPage("tutorial")}
              />
              <ContactButton
                active={page === "contact"}
                onClick={() => setPage("contact")}
              />
              <SettingsButton
                active={page === "settings"}
                onClick={() => setPage("settings")}
              />
              <ThemeToggle theme={theme} onToggle={toggleTheme} />
            </div>
          </div>
          <div className="content-area-doc">
            {page === "settings" ? (
              <SettingsPage
                mode={ws.mode}
                onChangeMode={ws.setMode}
                isRunning={ws.isRunning}
                models={modelHook.models}
                modelSelection={modelHook.selection}
                workerPinned={modelHook.workerPinned}
                onChangeOrchestrationModel={modelHook.setOrchestration}
                onChangeWorkerModel={modelHook.setWorker}
                onResetWorkerModel={modelHook.unpinWorker}
                modelKeys={modelHook.keys}
                onSaveApiKey={modelHook.setApiKey}
              />
            ) : page === "tutorial" ? (
              <TutorialPage />
            ) : page === "contact" ? (
              <ContactPage />
            ) : (
              <MetricsPage metrics={ws.metrics} />
            )}
          </div>
        </main>
      </div>
    );
  }

  // ─── Three-column layout ─────────────────────────────────────────
  // [ Sidebar (Projects + Files) | Chat | Plan ]
  //
  // Project + library files live in the left sidebar; the middle
  // column is always the chat. The old standalone "Files" top-nav
  // page was removed — the sidebar covers the same surface area.
  return (
    <div className="app-layout">
      <Sidebar
        width={sidebarWidth}
        sessions={session.sessions}
        currentProjectId={session.currentProjectId}
        currentProjectTitle={currentProjectTitle}
        onFetchSessions={session.fetchSessions}
        onNewProject={handleClearSession}
        onLoad={handleLoadSession}
        onDelete={session.deleteSession}
        hasMessages={ws.messages.length > 0}
        fileBrowserRefreshKey={fileBrowserRefreshKey}
        onUploadToLibrary={handleUploadToLibrary}
        onUploadToProject={handleUploadToProject}
      />

      <Splitter
        orientation="vertical"
        onResize={resizeSidebar}
        ariaLabel="Resize sidebar"
      />

      <main className="main-area">
        <div className="top-bar">
          <button
            type="button"
            className="app-brand app-brand-button"
            onClick={() => setPage("chat")}
            aria-label="Return to chat"
            title="Return to chat"
          >
            <img
              src="/tissueagent-icon.png"
              alt=""
              aria-hidden="true"
              className="app-logo"
            />
            <h1 className="app-title">TissueAgent</h1>
          </button>
          <div className="top-bar-right">
            <div
              className={`connection-status status-${ws.connectionStatus}`}
              role="status"
              aria-live="polite"
            >
              <span className={`status-dot ${ws.connectionStatus}`} />
              {ws.connectionStatus === "connected"
                ? "Connected"
                : ws.connectionStatus === "connecting"
                  ? "Connecting…"
                  : "Disconnected"}
            </div>
            <MetricsButton
              active={false}
              onClick={() => setPage("metrics")}
            />
            <TutorialButton
              active={false}
              onClick={() => setPage("tutorial")}
            />
            <ContactButton
              active={false}
              onClick={() => setPage("contact")}
            />
            <SettingsButton
              active={false}
              onClick={() => setPage("settings")}
            />
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
              enableDebug={true}
              projectId={session.currentProjectId}
              onSendMessage={ws.sendMessage}
              onCancelRun={ws.cancelRun}
              onUploadFiles={handleUploadToProject}
            />
          </div>
        </div>
      </main>

      <Splitter
        orientation="vertical"
        onResize={(delta) => resizePlanCol(-delta)}
        ariaLabel="Resize plan column"
      />

      <PlanColumn
        width={planColWidth}
        plan={planHook.plan}
        planMarkdown={planHook.markdown}
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
      />
    </div>
  );
}
