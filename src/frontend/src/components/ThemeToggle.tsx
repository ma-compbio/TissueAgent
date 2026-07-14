import type { Theme } from "../hooks/useTheme";

interface Props {
  theme: Theme;
  onToggle: () => void;
}

/**
 * Light/dark toggle. Renders in the top-bar-right cluster alongside the
 * Tutorial / Contact / Settings icons, so it inherits the same
 * ``.top-bar-icon-btn`` chrome and tooltip styling — one visual family
 * for the whole top bar. The visible glyph swaps based on the current
 * theme: a crescent moon when light (clicking goes to dark) and a sun
 * when dark (clicking goes to light).
 */
export default function ThemeToggle({ theme, onToggle }: Props) {
  const next = theme === "light" ? "dark" : "light";
  const label = `Switch to ${next} mode`;

  return (
    <button
      type="button"
      className="top-bar-icon-btn"
      onClick={onToggle}
      aria-label={label}
    >
      {theme === "light" ? (
        // Crescent moon — solid-ish stroke at 1.6 to match the other icons.
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
          <path d="M20.5 14.4a8.5 8.5 0 0 1-10.9-10.9 8.5 8.5 0 1 0 10.9 10.9z" />
        </svg>
      ) : (
        // Sun — same stroke as moon for balanced visual weight.
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
          <circle cx="12" cy="12" r="4.2" />
          {/* Eight rays — short, evenly spaced, kept inside a 24px box so
              the sun feels balanced against the crescent at the same size. */}
          <path d="M12 2.5v2.4" />
          <path d="M12 19.1v2.4" />
          <path d="M2.5 12h2.4" />
          <path d="M19.1 12h2.4" />
          <path d="M5.2 5.2l1.7 1.7" />
          <path d="M17.1 17.1l1.7 1.7" />
          <path d="M5.2 18.8l1.7-1.7" />
          <path d="M17.1 6.9l1.7-1.7" />
        </svg>
      )}
      <span className="top-bar-icon-tooltip" role="tooltip">
        {label}
      </span>
    </button>
  );
}
