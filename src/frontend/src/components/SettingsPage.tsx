/**
 * Settings page — two sections:
 *   1. Agent Settings  – backend/agent behaviour (models, limits, modes, etc.)
 *   2. Display Settings – frontend appearance (theme, layout, debug flags, etc.)
 *
 * Layout conventions:
 *   - Outer wrapper uses `.doc-page` so it inherits the same max-width,
 *     margins and typography as the Tutorial and Contact pages.
 *   - Each section is a `.settings-section` card.
 *   - Rows inside use `.settings-row` (label + control side-by-side, description below).
 *   - Security/warning notices use `.settings-help-box` with a `warning` modifier.
 */

import { useSettings } from "../hooks/useSettings";

export default function SettingsPage() {
  const { settings, saving, error, setSandboxEnabled } = useSettings();

  const sandboxEnabled = settings?.sandbox_enabled ?? true;

  return (
    <article className="doc-page settings-page">
      <header className="doc-header">
        <p className="doc-eyebrow">Configuration</p>
        <h1 className="doc-title">Settings</h1>
      </header>

      {error && <p className="settings-error">{error}</p>}

      {/* ── Agent Settings ─────────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section-title">Agent</h2>
        <p className="settings-section-desc">
          Configure agent behaviour, model selection, execution limits, and
          other backend parameters.
        </p>
        <div className="settings-rows">

          {/* Docker Sandbox */}
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
              Kernel Gateway). Enabled by default. Requires Docker to be
              available on the host. Changes to this setting take effect on
              the next agent run; Docker start/stop requires a server restart.
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

          {/* Add more agent setting rows here */}
        </div>
      </section>

      {/* ── Display Settings ───────────────────────────────────────── */}
      <section className="settings-section">
        <h2 className="settings-section-title">Display</h2>
        <p className="settings-section-desc">
          Adjust the appearance and layout of the frontend interface.
        </p>
        <div className="settings-rows">
          {/* TODO: add display setting rows here */}
          <p className="settings-empty">No display settings configured yet.</p>
        </div>
      </section>
    </article>
  );
}
