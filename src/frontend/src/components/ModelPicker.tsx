import type { ModelOption, ModelSelection } from "../hooks/useModels";

interface Props {
  models: ModelOption[];
  selection: ModelSelection | null;
  workerPinned: boolean;
  onChangeOrchestration: (id: string) => void;
  onChangeWorker: (id: string) => void;
  onResetWorker: () => void;
  disabled?: boolean;
}

function groupByProvider(models: ModelOption[]) {
  const openai = models.filter((m) => m.provider === "openai");
  const anthropic = models.filter((m) => m.provider === "anthropic");
  return { openai, anthropic };
}

function renderOptions(models: ModelOption[]) {
  const { openai, anthropic } = groupByProvider(models);
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
    </>
  );
}

export default function ModelPicker({
  models,
  selection,
  workerPinned,
  onChangeOrchestration,
  onChangeWorker,
  onResetWorker,
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
    </div>
  );
}
