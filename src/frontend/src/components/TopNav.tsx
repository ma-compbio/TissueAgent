/**
 * Top-bar navigation between the three pages. Used inside ``App``.
 * Pure presentational — the page state lives in App.
 */

import type { Page } from "../App";

interface Props {
  current: Page;
  onNavigate: (page: Page) => void;
}

const ITEMS: Array<{ key: Page; label: string }> = [
  { key: "chat", label: "Chat" },
  { key: "files", label: "Files" },
  { key: "settings", label: "Settings" },
  { key: "tutorial", label: "Tutorial" },
  { key: "contact", label: "Contact" },
];

export default function TopNav({ current, onNavigate }: Props) {
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
