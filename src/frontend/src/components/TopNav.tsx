/**
 * Top-bar navigation between pages. Settings is rendered separately as a
 * gear icon in the top-bar-right (see ``SettingsButton`` below). The nav
 * row keeps the user-facing destinations: Chat, Files, Tutorial, Contact.
 */

import type { Page } from "../App";

interface NavProps {
  current: Page;
  onNavigate: (page: Page) => void;
}

const ITEMS: Array<{ key: Page; label: string }> = [
  { key: "chat", label: "Chat" },
  { key: "tutorial", label: "Tutorial" },
  { key: "contact", label: "Contact" },
];

export default function TopNav({ current, onNavigate }: NavProps) {
  return (
    <nav className="top-nav" aria-label="Primary">
      {ITEMS.map((item) => (
        <button
          key={item.key}
          type="button"
          className={`top-nav-item ${current === item.key ? "active" : ""}`}
          onClick={() => onNavigate(item.key)}
          aria-current={current === item.key ? "page" : undefined}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}

interface SettingsButtonProps {
  active: boolean;
  onClick: () => void;
}

/** Gear icon. Lives in the top-right area, not in the main nav row. */
export function SettingsButton({ active, onClick }: SettingsButtonProps) {
  return (
    <button
      type="button"
      className={`top-bar-icon-btn ${active ? "active" : ""}`}
      onClick={onClick}
      aria-label="Open settings"
      aria-current={active ? "page" : undefined}
      title="Settings"
    >
      <svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.36.13.7.36.97.62.27.27.49.6.62.97.13.36.18.74.18 1.12s-.05.76-.18 1.12c-.13.36-.35.7-.62.97-.27.27-.61.49-.97.62z" />
      </svg>
    </button>
  );
}
