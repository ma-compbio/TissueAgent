/**
 * Settings page — single column of configuration sections.
 *
 *   1. Mode         – autopilot vs copilot
 *   2. Models       – orchestration + worker model selection + API keys
 *   3. Agent        – Docker sandbox toggle (and other backend behaviour)
 *   4. Display      – frontend appearance settings
 *
 * Layout: outer `.doc-page` matches Tutorial/Contact for typography and
 * width; each block is a `.settings-section` card with rows inside.
 */

import ModelPicker from "./ModelPicker";
import type {
  KeyStatusMap,
  ModelOption,
  ModelSelection,
  Provider,
} from "../hooks/useModels";
import type { SessionMode } from "../types/messages";
import { useSettings } from "../hooks/useSettings";

interface Props {
  mode: SessionMode;
  onChangeMode: (mode: SessionMode) => void;
  isRunning: boolean;
  models: ModelOption[];
  modelSelection: ModelSelection | null;
  workerPinned: boolean;
  onChangeOrchestrationModel: (id: string) => void;
  onChangeWorkerModel: (id: string) => void;
  onResetWorkerModel: () => void;
  modelKeys: KeyStatusMap;
  onSaveApiKey: (provider: Provider, key: string) => Promise<boolean>;
}

export default function SettingsPage({
  mode,
  onChangeMode,
  isRunning,
  models,
  modelSelection,
  workerPinned,
  onChangeOrchestrationModel,
  onChangeWorkerModel,
  onResetWorkerModel,
  modelKeys,
  onSaveApiKey,
}: Props) {
  const { settings, saving, error, setSandboxEnabled } = useSettings();
  const sandboxEnabled = settings?.sandbox_enabled ?? true;

  return (
    <article className="doc-page settings-page">
      <header className="doc-header">
        <p className="doc-eyebrow">Configuration</p>
        <h1 className="doc-title">Settings</h1>
      </header>

      {error && <p className="settings-error">{error}</p>}

      {/* ── Mode ───────────────────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section-title">Execution mode</h2>
        <p className="settings-section-desc">
          How the agent pipeline runs from prompt to final report.
        </p>
        <div className="settings-rows">
          <div className="settings-row">
            <div
              className="settings-mode-choices"
              role="radiogroup"
              aria-label="Execution mode"
            >
              <label
                className={`settings-mode-choice ${mode === "autopilot" ? "active" : ""}`}
              >
                <input
                  type="radio"
                  name="execution-mode"
                  value="autopilot"
                  checked={mode === "autopilot"}
                  onChange={() => onChangeMode("autopilot")}
                />
                <span className="settings-mode-choice-title">Autopilot</span>
                <span className="settings-mode-choice-body">
                  The agent runs end-to-end without pauses. Planner →
                  Recruiter → Manager → Evaluator → Reporter, all
                  automatic. Use when you trust the plan or just want
                  results.
                </span>
              </label>

              <label
                className={`settings-mode-choice ${mode === "copilot" ? "active" : ""}`}
              >
                <input
                  type="radio"
                  name="execution-mode"
                  value="copilot"
                  checked={mode === "copilot"}
                  onChange={() => onChangeMode("copilot")}
                />
                <span className="settings-mode-choice-title">Copilot</span>
                <span className="settings-mode-choice-body">
                  The agent pauses twice for your review — once after
                  the planner drafts the plan, and again after the
                  recruiter assigns agents. At each pause you can
                  approve, edit, send feedback, or cancel.
                </span>
              </label>
            </div>
            {isRunning && (
              <p className="settings-row-desc">
                A run is in progress. The change takes effect on the next prompt.
              </p>
            )}
          </div>
        </div>
      </section>

      {/* ── Models + API keys ──────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section-title">Models &amp; API keys</h2>
        <p className="settings-section-desc">
          Pick the orchestration and worker models, and supply API keys
          for the providers you'd like to use. Keys are stored on the
          server and never sent back to the browser.
        </p>
        <div className="settings-models-host">
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
        </div>
      </section>

      {/* ── Agent ──────────────────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section-title">Agent</h2>
        <p className="settings-section-desc">
          Configure agent behaviour and execution environment.
        </p>
        <div className="settings-rows">

          <div className="settings-row">
            <div className="settings-row-header">
              <label className="settings-row-label" htmlFor="sandbox-toggle">
                Docker sandbox
              </label>
              <button
                id="sandbox-toggle"
                type="button"
                role="switch"
                aria-checked={sandboxEnabled}
                disabled={saving || settings === null}
                className={`settings-toggle ${sandboxEnabled ? "on" : "off"}`}
                onClick={() => setSandboxEnabled(!sandboxEnabled)}
              >
                <span className="settings-toggle-thumb" />
                <span className="settings-toggle-label">
                  {sandboxEnabled ? "Enabled" : "Disabled"}
                </span>
              </button>
            </div>
            <p className="settings-row-desc">
              Run code execution inside an isolated Docker container (Jupyter
              Kernel Gateway). Disabled by default so the server can boot
              without Docker running. Requires the Docker daemon to be
              available on the host when enabled. Changes take effect on the
              next agent run; Docker start/stop requires a server restart.
            </p>

            {!sandboxEnabled && (
              <div className="settings-help-box warning" role="alert">
                <span className="settings-help-box-icon">⚠</span>
                <div className="settings-help-box-body">
                  <strong>Security notice — sandbox disabled</strong>
                  <p>
                    When the Docker sandbox is off, the Execution Agent runs
                    code directly on the host machine via a local Jupyter
                    kernel. The agent can execute arbitrary code with the same
                    privileges as the server process, including reading and
                    writing files anywhere on the filesystem.
                  </p>
                  <p>
                    A strict file-access policy is injected into the agent
                    prompt restricting operations to{" "}
                    <code>/workspace</code> (DATA_DIR), but this is a
                    prompt-level guardrail only — it is not enforced at the OS
                    level. Only disable the sandbox in trusted, controlled
                    environments.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Display ────────────────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section-title">Display</h2>
        <p className="settings-section-desc">
          Adjust the appearance and layout of the frontend interface.
        </p>
        <div className="settings-rows">
          <p className="settings-empty">No display settings configured yet.</p>
        </div>
      </section>
    </article>
  );
}
