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

export default function AgentAvatar({
  name,
  fallback,
  size = 20,
  className,
}: Props) {
  const iconSrc = name ? MAIN_AGENT_ICON[name] : undefined;
  const cls = `avatar agent-avatar${className ? " " + className : ""}`;

  if (iconSrc) {
    return (
      <span
        className={cls}
        style={{ width: size, height: size, display: "inline-flex" }}
      >
        <img
          src={iconSrc}
          alt={PRETTY_LABEL[name!] ?? ""}
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
