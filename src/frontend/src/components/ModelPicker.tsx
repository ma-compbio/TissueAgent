import { useEffect, useState } from "react";
import type {
  KeyStatusMap,
  ModelOption,
  ModelSelection,
  Provider,
} from "../hooks/useModels";

interface Props {
  models: ModelOption[];
  selection: ModelSelection | null;
  workerPinned: boolean;
  onChangeOrchestration: (id: string) => void;
  onChangeWorker: (id: string) => void;
  onResetWorker: () => void;
  keys: KeyStatusMap;
  onSaveKey: (provider: Provider, key: string) => Promise<boolean>;
  disabled?: boolean;
}

function groupByProvider(models: ModelOption[]) {
  const openai = models.filter((m) => m.provider === "openai");
  const anthropic = models.filter((m) => m.provider === "anthropic");
  const openrouter = models.filter((m) => m.provider === "openrouter");
  return { openai, anthropic, openrouter };
}

function renderOptions(models: ModelOption[]) {
  const { openai, anthropic, openrouter } = groupByProvider(models);
  return (
    <>
      {openai.length > 0 && (
        <optgroup label="OpenAI">
          {openai.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </optgroup>
      )}
      {anthropic.length > 0 && (
        <optgroup label="Anthropic">
          {anthropic.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </optgroup>
      )}
      {openrouter.length > 0 && (
        <optgroup label="OpenRouter">
          {openrouter.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </optgroup>
      )}
    </>
  );
}

const PROVIDER_LABEL: Record<Provider, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  openrouter: "OpenRouter",
};

const PROVIDER_LINK: Record<Provider, string> = {
  openai: "https://platform.openai.com/api-keys",
  anthropic: "https://console.anthropic.com/settings/keys",
  openrouter: "https://openrouter.ai/keys",
};

interface ApiKeyRowProps {
  provider: Provider;
  status: { env_var: string; env_set: boolean; ui_set: boolean; effective: boolean } | undefined;
  onSave: (provider: Provider, key: string) => Promise<boolean>;
  disabled?: boolean;
}

function ApiKeyRow({ provider, status, onSave, disabled }: ApiKeyRowProps) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Briefly show a "saved" indicator after a successful submit.
  useEffect(() => {
    if (savedAt === null) return;
    const t = setTimeout(() => setSavedAt(null), 1800);
    return () => clearTimeout(t);
  }, [savedAt]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    const ok = await onSave(provider, value);
    setSaving(false);
    if (ok) {
      setValue("");
      setSavedAt(Date.now());
    }
  };

  const handleClear = async () => {
    setSaving(true);
    const ok = await onSave(provider, "");
    setSaving(false);
    if (ok) {
      setValue("");
      setSavedAt(Date.now());
    }
  };

  const envSet = status?.env_set ?? false;
  const uiSet = status?.ui_set ?? false;
  const effective = status?.effective ?? false;

  let statusText: string;
  if (uiSet) statusText = "key stored from UI";
  else if (envSet) statusText = `using env var ${status?.env_var}`;
  else statusText = "no key";

  const placeholder = uiSet
    ? "key set — paste a new one to replace"
    : envSet
      ? `using ${status?.env_var} — paste to override`
      : "paste your API key";

  return (
    <form className="api-key-row" onSubmit={handleSubmit}>
      <div className="api-key-row-head">
        <span className="api-key-row-label">
          {PROVIDER_LABEL[provider]}
          <span
            className={`api-key-dot ${effective ? "ok" : "missing"}`}
            aria-hidden="true"
            title={effective ? "API key available" : "no API key set"}
          />
        </span>
        <a
          href={PROVIDER_LINK[provider]}
          target="_blank"
          rel="noreferrer noopener"
          className="api-key-link"
        >
          get key →
        </a>
      </div>
      <div className="api-key-row-input">
        <input
          type="password"
          className="api-key-input"
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled || saving}
        />
        <button
          type="submit"
          className="api-key-save"
          disabled={disabled || saving || !value.trim()}
        >
          save
        </button>
      </div>
      <div className="api-key-row-status">
        <span>{statusText}</span>
        {uiSet && (
          <button
            type="button"
            className="api-key-clear"
            onClick={handleClear}
            disabled={disabled || saving}
            title="Clear UI key and fall back to env var"
          >
            clear
          </button>
        )}
        {savedAt !== null && <span className="api-key-saved">saved ✓</span>}
      </div>
    </form>
  );
}

export default function ModelPicker({
  models,
  selection,
  workerPinned,
  onChangeOrchestration,
  onChangeWorker,
  onResetWorker,
  keys,
  onSaveKey,
  disabled,
}: Props) {
  if (!selection || models.length === 0) {
    return (
      <div className="model-picker">
        <div className="model-picker-title">Model</div>
        <div className="model-picker-loading">Loading models…</div>
      </div>
    );
  }

  const providers: Provider[] = ["openai", "anthropic", "openrouter"];

  return (
    <div className="model-picker">
      <div className="model-picker-title">Model</div>

      <label className="model-picker-row">
        <span className="model-picker-label">Orchestration Agents</span>
        <select
          className="model-picker-select"
          value={selection.orchestration}
          onChange={(e) => onChangeOrchestration(e.target.value)}
          disabled={disabled}
        >
          {renderOptions(models)}
        </select>
      </label>

      <label className="model-picker-row">
        <span className="model-picker-label">
          Expert Agents
          {workerPinned && (
            <button
              type="button"
              className="model-picker-reset"
              onClick={onResetWorker}
              title="Match orchestration agents model"
            >
              sync
            </button>
          )}
        </span>
        <select
          className="model-picker-select"
          value={selection.worker}
          onChange={(e) => onChangeWorker(e.target.value)}
          disabled={disabled}
        >
          {renderOptions(models)}
        </select>
      </label>

      <div className="model-picker-hint">
        Applies on next message.
      </div>

      <details className="api-keys-section">
        <summary className="api-keys-summary">API keys</summary>
        <div className="api-keys-body">
          {providers.map((p) => (
            <ApiKeyRow
              key={p}
              provider={p}
              status={keys[p]}
              onSave={onSaveKey}
              disabled={disabled}
            />
          ))}
          <div className="api-keys-note">
            Keys typed here are kept in server memory only and override the
            matching environment variable until cleared.
          </div>
        </div>
      </details>
    </div>
  );
}
