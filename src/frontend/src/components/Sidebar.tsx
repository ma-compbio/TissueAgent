import type { FileInfo, SessionInfo, SessionMode } from "../types/messages";
import type {
  KeyStatusMap,
  ModelOption,
  ModelSelection,
  Provider,
} from "../hooks/useModels";
import type { Plan } from "../hooks/usePlan";
import type { AgentInfo } from "../hooks/useAgents";
import type { PipelineStage, ReviewState } from "../hooks/useWebSocket";
import FileUpload from "./FileUpload";
import ModelPicker from "./ModelPicker";
import PlanPanel from "./PlanPanel";
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
  plan: Plan;
  planMarkdown: string;
  isRunning: boolean;
  mode: SessionMode;
  onChangeMode: (mode: SessionMode) => void;
  reviewState: ReviewState;
  pipelineStage: PipelineStage | null;
  agents: AgentInfo[];
  onApprovePlan: () => void;
  onEditPlan: (markdown: string) => void;
  onPlanFeedback: (text: string) => void;
  onApproveAssignments: () => void;
  onEditAssignments: (markdown: string) => void;
  onAssignmentsFeedback: (text: string) => void;
  onCancelRun: () => void;
  models: ModelOption[];
  modelSelection: ModelSelection | null;
  workerPinned: boolean;
  onChangeOrchestrationModel: (id: string) => void;
  onChangeWorkerModel: (id: string) => void;
  onResetWorkerModel: () => void;
  modelKeys: KeyStatusMap;
  onSaveApiKey: (provider: Provider, key: string) => Promise<boolean>;
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
  plan,
  planMarkdown,
  isRunning,
  mode,
  onChangeMode,
  reviewState,
  pipelineStage,
  agents,
  onApprovePlan,
  onEditPlan,
  onPlanFeedback,
  onApproveAssignments,
  onEditAssignments,
  onAssignmentsFeedback,
  onCancelRun,
  models,
  modelSelection,
  workerPinned,
  onChangeOrchestrationModel,
  onChangeWorkerModel,
  onResetWorkerModel,
  modelKeys,
  onSaveApiKey,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <FileUpload
          uploadedFiles={uploadedFiles}
          onUploadFiles={onUploadFiles}
        />

        <div className="upload-divider" />

        <ModelPicker
          models={models}
          selection={modelSelection}
          workerPinned={workerPinned}
          onChangeOrchestration={onChangeOrchestrationModel}
          onChangeWorker={onChangeWorkerModel}
          onResetWorker={onResetWorkerModel}
          keys={modelKeys}
          onSaveKey={onSaveApiKey}
          disabled={isRunning}
        />

        <div className="upload-divider" />

        <div className="mode-toggle" role="radiogroup" aria-label="Execution mode">
          <button
            type="button"
            role="radio"
            aria-checked={mode === "autopilot"}
            className={`mode-pill ${mode === "autopilot" ? "active" : ""}`}
            onClick={() => onChangeMode("autopilot")}
            disabled={isRunning}
            title="Run end-to-end without pausing for review"
          >
            Autopilot
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === "copilot"}
            className={`mode-pill ${mode === "copilot" ? "active" : ""}`}
            onClick={() => onChangeMode("copilot")}
            disabled={isRunning}
            title="Pause for review after the plan and after agent assignment"
          >
            Copilot
          </button>
        </div>

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
        <PlanPanel
          plan={plan}
          markdown={planMarkdown}
          reviewState={reviewState}
          pipelineStage={pipelineStage}
          agents={agents}
          onApprovePlan={onApprovePlan}
          onEditPlan={onEditPlan}
          onPlanFeedback={onPlanFeedback}
          onApproveAssignments={onApproveAssignments}
          onEditAssignments={onEditAssignments}
          onAssignmentsFeedback={onAssignmentsFeedback}
          onCancelRun={onCancelRun}
        />
      </div>
    </aside>
  );
}
