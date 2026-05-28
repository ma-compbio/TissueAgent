/**
 * Renders an agent avatar. When the agent name matches one of the
 * orchestration agents (planner / recruiter / manager / evaluator /
 * reporter) we use the custom PNG icon shipped in /public. Otherwise we
 * fall back to the emoji string carried on the serialized message.
 */

interface Props {
  /** Agent identifier from the serialized message, e.g. "manager_agent". */
  name?: string | null;
  /** Emoji avatar fallback. */
  fallback?: string;
  /** Visual size in pixels. */
  size?: number;
  /** Optional extra class on the wrapper span. */
  className?: string;
}

const MAIN_AGENT_ICON: Record<string, string> = {
  planner_agent: "/planner_icon.png",
  recruiter_agent: "/recruiter_icon.png",
  manager_agent: "/manager_icon.png",
  evaluator_agent: "/evaluator_icon.png",
  reporter_agent: "/reporter_icon.png",
};

const PRETTY_LABEL: Record<string, string> = {
  planner_agent: "Planner",
  recruiter_agent: "Recruiter",
  manager_agent: "Manager",
  evaluator_agent: "Evaluator",
  reporter_agent: "Reporter",
};

/* Display-name → canonical snake_case ID. Some callers (TracePanel,
   ``SubagentCard``, live-trace tiles in ``ChatView``) carry the
   user-facing label (e.g. "Planner", "Manager Agent") rather than the
   underlying agent_id. Normalize so any caller passing either form
   resolves to the same icon. */
const DISPLAY_NAME_TO_ID: Record<string, string> = {
  planner: "planner_agent",
  recruiter: "recruiter_agent",
  manager: "manager_agent",
  evaluator: "evaluator_agent",
  reporter: "reporter_agent",
  "planner agent": "planner_agent",
  "recruiter agent": "recruiter_agent",
  "manager agent": "manager_agent",
  "evaluator agent": "evaluator_agent",
  "reporter agent": "reporter_agent",
};

function _resolveIconKey(name?: string | null): string | undefined {
  if (!name) return undefined;
  if (MAIN_AGENT_ICON[name]) return name;
  // Try the display-name lookup with case + whitespace tolerance.
  const normalized = name.trim().toLowerCase();
  return DISPLAY_NAME_TO_ID[normalized];
}

export default function AgentAvatar({
  name,
  fallback,
  size = 20,
  className,
}: Props) {
  const iconKey = _resolveIconKey(name);
  const iconSrc = iconKey ? MAIN_AGENT_ICON[iconKey] : undefined;
  const cls = `avatar agent-avatar${className ? " " + className : ""}`;

  if (iconSrc && iconKey) {
    return (
      <span
        className={cls}
        style={{ width: size, height: size, display: "inline-flex" }}
      >
        <img
          src={iconSrc}
          alt={PRETTY_LABEL[iconKey] ?? ""}
          width={size}
          height={size}
          className="agent-avatar-img"
        />
      </span>
    );
  }

  return (
    <span
      className={cls}
      style={{ width: size, height: size, display: "inline-flex" }}
    >
      {fallback ?? ""}
    </span>
  );
}
