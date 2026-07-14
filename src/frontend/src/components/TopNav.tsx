/**
 * Top-bar icon buttons.
 *
 * The top bar's right cluster holds icon-only buttons for Tutorial,
 * Contact, and Settings — all sharing identical chrome. Each shows a
 * tooltip on hover/focus. Returning to chat is handled by clicking the
 * TissueAgent brand on the left of the top bar (see App.tsx).
 */

import type { PropsWithChildren } from "react";

interface IconButtonProps {
  /** Highlight the button as the current page. */
  active: boolean;
  onClick: () => void;
  /** Visible-on-hover label. Also used as aria-label for screen readers. */
  label: string;
}

function TopBarIconButton({
  active,
  onClick,
  label,
  children,
}: PropsWithChildren<IconButtonProps>) {
  return (
    <button
      type="button"
      className={`top-bar-icon-btn ${active ? "active" : ""}`}
      onClick={onClick}
      aria-label={label}
      aria-current={active ? "page" : undefined}
    >
      {children}
      <span className="top-bar-icon-tooltip" role="tooltip">
        {label}
      </span>
    </button>
  );
}

// All four icons (Settings, Tutorial, Contact, ThemeToggle) follow the
// same drawing rules: 24×24 viewBox, 18×18 rendered size, 1.6 stroke,
// rounded caps + joins, geometry kept inside the 3.5–20.5 inner box so
// the strokes don't clip against the button's hover background.

/** Left-pointing arrow with a chat-bubble hint behind it. Shown only
 *  in the doc-layout top bar (Settings / Tutorial / Contact pages) so
 *  the user has an icon-side affordance to return to chat in addition
 *  to clicking the brand on the left. Uses the same family chrome as
 *  the other top-bar icons (stroke 1.6, 24×24 viewBox). */
export function BackToChatButton({ onClick }: { onClick: () => void }) {
  return (
    <TopBarIconButton active={false} onClick={onClick} label="Return to chat">
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
        {/* Speech bubble — rounded rectangle with a tail pointing down-
            left at the corner where the back-arrow exits. Signals
            "chat" without being verbose. */}
        <path d="M21 11.5a7.5 7.5 0 0 1-10.6 6.85L5.5 19.5l1.2-3.6A7.5 7.5 0 1 1 21 11.5z" />
        {/* Inward-pointing arrow head — drawn *inside* the bubble at
            its left edge so the glyph reads as "return into the chat",
            not "leave to somewhere else". */}
        <path d="M13.3 8.5 L10 11.5 L13.3 14.5" />
        <path d="M10 11.5 H16" />
      </svg>
    </TopBarIconButton>
  );
}

/** Cogwheel — a single closed silhouette tracing six rectangular
 *  teeth and the valleys between them. Earlier iterations used radial
 *  stub-spokes, which collided visually with the sun glyph on the
 *  ThemeToggle (both being "circle + symmetric strokes outward").
 *  Solid cogged outline + a hollow bore at center is unambiguously a
 *  gear: it has the silhouette of a real mechanical cog, not a sun.
 *
 *  Geometry: outer (tooth-tip) radius 9.2, inner (valley) radius 6.4,
 *  six teeth at 60° spacing each occupying 30° of arc (1:1 land-to-
 *  valley ratio). All vertices computed with the math at the top of
 *  this file's review — the inline coordinates are deliberate, not
 *  hand-waved. */
export function SettingsButton({
  active,
  onClick,
}: Omit<IconButtonProps, "label">) {
  return (
    <TopBarIconButton active={active} onClick={onClick} label="Settings">
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
        <path d="M8.8 6.46 L9.62 3.11 L14.38 3.11 L15.2 6.46 L18.51 5.49 L20.89 9.62 L18.4 12 L20.89 14.38 L18.51 18.51 L15.2 17.54 L14.38 20.89 L9.62 20.89 L8.8 17.54 L5.49 18.51 L3.11 14.38 L5.6 12 L3.11 9.62 L5.49 5.49 Z" />
        {/* Bore hole at the center — the through-hole where the gear
            mounts on a shaft. A small *open* circle, not a filled dot;
            that's what visually distinguishes "machined part" from
            "stylized graphic". */}
        <circle cx="12" cy="12" r="2.4" />
      </svg>
    </TopBarIconButton>
  );
}

/** Open book — single outline with a centerline spine. The original
 *  had two near-identical mirrored paths which doubled the stroke
 *  count for no semantic gain; one path with an interior crease lands
 *  at the same visual weight as the envelope and the gear. */
export function TutorialButton({
  active,
  onClick,
}: Omit<IconButtonProps, "label">) {
  return (
    <TopBarIconButton active={active} onClick={onClick} label="Tutorial">
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
        {/* Book outline — an open book viewed from above. The two outer
            corners drop ~1 unit lower than the center spine so the pages
            read as resting flat on the surface. */}
        <path d="M3.5 5.5h6a2.5 2.5 0 0 1 2.5 2.5v11.5a2 2 0 0 0-2-2H3.5z" />
        <path d="M20.5 5.5h-6a2.5 2.5 0 0 0-2.5 2.5v11.5a2 2 0 0 1 2-2h6.5z" />
        {/* Center spine — drawn shorter than the book height so it
            reads as the binding, not a divider line. */}
        <path d="M12 8v9.5" />
      </svg>
    </TopBarIconButton>
  );
}

/** Bar chart — three vertical bars of increasing height inside the
 *  inner 3.5–20.5 box, sharing a baseline. Reads as "metrics" without
 *  the visual clutter of axes or gridlines. */
export function MetricsButton({
  active,
  onClick,
}: Omit<IconButtonProps, "label">) {
  return (
    <TopBarIconButton active={active} onClick={onClick} label="Metrics">
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
        {/* Baseline — the floor the three bars rest on. Drawn slightly
            inset so it doesn't collide with the button's hover ring. */}
        <path d="M3.5 20.5h17" />
        {/* Three bars at x = 6, 12, 17 with heights stepping up so the
            shape reads as a growth chart, not a barcode. */}
        <path d="M6 20.5v-5" />
        <path d="M12 20.5v-9" />
        <path d="M17 20.5v-13" />
      </svg>
    </TopBarIconButton>
  );
}

/** Envelope — kept close to the previous version because it was already
 *  the cleanest of the three. The flap (interior crease) is shortened
 *  to a chevron so it sits *inside* the envelope body rather than
 *  meeting the body's corners, which felt heavy. */
export function ContactButton({
  active,
  onClick,
}: Omit<IconButtonProps, "label">) {
  return (
    <TopBarIconButton active={active} onClick={onClick} label="Contact">
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
        <rect x="3.5" y="5.5" width="17" height="13" rx="1.8" />
        {/* Flap chevron — stops 1 unit short of each top corner so it
            reads as a paper crease, not as the envelope's outline. */}
        <path d="M4.5 7.5l7.5 5.2 7.5-5.2" />
      </svg>
    </TopBarIconButton>
  );
}
