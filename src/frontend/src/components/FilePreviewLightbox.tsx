/**
 * Full-screen file previewer.
 *
 * Opens over a dimmed backdrop and shows the requested file at a
 * comfortable size. Supports:
 *   - Images (png/jpg/jpeg/gif/webp/svg/tif/tiff) — rendered as <img>.
 *   - Text-ish files (txt/md/csv/tsv/json/log/yaml/yml/py/r) — fetched
 *     and shown in a monospace pane, capped at TEXT_PREVIEW_MAX_BYTES.
 *   - Anything else — a one-line "no preview" stub with a download link.
 *
 * Keyboard: Esc closes, ArrowLeft/ArrowRight walk siblings.
 *
 * The component is *display-only*. State (which item is open, the
 * sibling list) lives in the parent so it can be shared between
 * multiple BrowserPane instances.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

/** Cap for inline text previews. Above this, show a "file too large"
 *  notice with a download link. 256 KB is enough for most logs / CSVs
 *  the user will want to glance at; bigger artifacts should be opened
 *  externally. */
const TEXT_PREVIEW_MAX_BYTES = 256 * 1024;

const IMAGE_EXTS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".tif", ".tiff",
]);
const TEXT_EXTS = new Set([
  ".txt", ".md", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml",
  ".py", ".r", ".sh", ".html", ".css", ".js", ".ts", ".tsx",
  ".jsx", ".toml", ".ini", ".env",
]);

type FileKind = "image" | "text" | "binary";

function classify(name: string): FileKind {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return "binary";
  const ext = name.slice(dot).toLowerCase();
  if (IMAGE_EXTS.has(ext)) return "image";
  if (TEXT_EXTS.has(ext)) return "text";
  return "binary";
}

export interface PreviewItem {
  /** Path relative to the scope root, as returned by /api/files/browse. */
  path: string;
  /** Display name (last segment of path). */
  name: string;
  /** Which API scope the file came from. */
  scope: "library" | "project";
  /** Required when scope === "project". */
  projectId?: string;
}

interface Props {
  /** Items to navigate between (typically all leaf files in the open
   *  pane). Used for prev/next arrows. */
  items: PreviewItem[];
  /** Currently-open index into items. */
  index: number;
  onClose: () => void;
  onIndexChange: (next: number) => void;
  /** Jump the matching pane to a folder path and close the lightbox.
   *  Used by clickable breadcrumb segments in the header. */
  onJumpToPath?: (scope: "library" | "project", path: string) => void;
}

/** Split ``a/b/c`` into ``[{name:'a', path:'a'}, {name:'b', path:'a/b'}, ...]``. */
function breadcrumbSegments(path: string): Array<{ name: string; path: string }> {
  if (!path) return [];
  const parts = path.split("/").filter(Boolean);
  const out: Array<{ name: string; path: string }> = [];
  let acc = "";
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p;
    out.push({ name: p, path: acc });
  }
  return out;
}

function buildUrl(item: PreviewItem): string {
  const qs = new URLSearchParams({ scope: item.scope });
  if (item.projectId) qs.set("project_id", item.projectId);
  return `${API}/api/files/download/${item.path}?${qs}`;
}

export default function FilePreviewLightbox({
  items,
  index,
  onClose,
  onIndexChange,
  onJumpToPath,
}: Props) {
  const item = items[index];
  const kind = useMemo(() => (item ? classify(item.name) : "binary"), [item]);
  const url = useMemo(() => (item ? buildUrl(item) : ""), [item]);

  const [textBody, setTextBody] = useState<string | null>(null);
  const [textError, setTextError] = useState<string | null>(null);
  const [textTruncated, setTextTruncated] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // Reset transient state whenever the active item changes.
  useEffect(() => {
    setTextBody(null);
    setTextError(null);
    setTextTruncated(false);
  }, [item?.path]);

  // For text files, fetch the body (with a size cap).
  useEffect(() => {
    if (!item || kind !== "text") return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const truncated = blob.size > TEXT_PREVIEW_MAX_BYTES;
        const sliced = truncated
          ? blob.slice(0, TEXT_PREVIEW_MAX_BYTES)
          : blob;
        const text = await sliced.text();
        if (cancelled) return;
        setTextBody(text);
        setTextTruncated(truncated);
      } catch (e) {
        if (!cancelled) {
          setTextError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [item, kind, url]);

  // Keyboard nav.
  const next = useCallback(() => {
    if (items.length === 0) return;
    onIndexChange((index + 1) % items.length);
  }, [index, items.length, onIndexChange]);
  const prev = useCallback(() => {
    if (items.length === 0) return;
    onIndexChange((index - 1 + items.length) % items.length);
  }, [index, items.length, onIndexChange]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        prev();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, next, prev]);

  // Focus the card on mount so Esc/arrow keys land on us, not stray
  // background controls.
  useEffect(() => {
    cardRef.current?.focus();
  }, []);

  if (!item) return null;

  const hasSiblings = items.length > 1;

  return (
    <div
      className="lightbox-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={`Preview: ${item.name}`}
      onClick={(e) => {
        // Clicks on the backdrop (not the card) close.
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={cardRef}
        className="lightbox-card"
        tabIndex={-1}
      >
        <header className="lightbox-header">
          <div className="lightbox-title-block">
            <span className="lightbox-filename" title={item.path}>
              {item.name}
            </span>
            <nav
              className="lightbox-breadcrumb"
              aria-label={`Path to ${item.name}`}
            >
              {(() => {
                // Build segments including the scope root, e.g.
                //   [Library, datasets, spatial, foo.h5ad]
                // The scope root and every directory segment is
                // clickable: click closes the lightbox and navigates
                // the matching pane to that folder. The final segment
                // (the file itself) is rendered as plain text.
                const segs = breadcrumbSegments(item.path);
                const rootLabel = item.scope === "library" ? "Library" : "Project";
                return (
                  <>
                    <button
                      type="button"
                      className="lightbox-crumb"
                      onClick={() => onJumpToPath?.(item.scope, "")}
                      disabled={!onJumpToPath}
                      title={`Open ${rootLabel}`}
                    >
                      {rootLabel}
                    </button>
                    {segs.map((seg, i) => {
                      const isLast = i === segs.length - 1;
                      return (
                        <span key={seg.path} className="lightbox-crumb-segment">
                          <span className="lightbox-crumb-sep" aria-hidden="true">
                            /
                          </span>
                          {isLast ? (
                            <span className="lightbox-crumb-leaf">
                              {seg.name}
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="lightbox-crumb"
                              onClick={() =>
                                onJumpToPath?.(item.scope, seg.path)
                              }
                              disabled={!onJumpToPath}
                              title={`Open ${seg.name}/`}
                            >
                              {seg.name}
                            </button>
                          )}
                        </span>
                      );
                    })}
                  </>
                );
              })()}
            </nav>
          </div>
          <div className="lightbox-actions">
            <a
              href={url}
              download={item.name}
              className="lightbox-action-btn"
              title="Download"
              aria-label="Download file"
            >
              <svg
                viewBox="0 0 16 16"
                width="14"
                height="14"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M8 3v8M4.5 7.5L8 11l3.5-3.5M3 13h10" />
              </svg>
            </a>
            <button
              type="button"
              className="lightbox-action-btn"
              onClick={onClose}
              title="Close (Esc)"
              aria-label="Close preview"
            >
              <svg
                viewBox="0 0 16 16"
                width="14"
                height="14"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              >
                <path d="M3 3l10 10M13 3L3 13" />
              </svg>
            </button>
          </div>
        </header>

        <div className="lightbox-body">
          {kind === "image" && (
            <img
              src={url}
              alt={item.name}
              className="lightbox-image"
            />
          )}

          {kind === "text" && (
            <pre className="lightbox-text">
              {textError && `Failed to load preview: ${textError}`}
              {!textError && textBody === null && "Loading…"}
              {!textError && textBody !== null && textBody}
              {textTruncated && (
                <span className="lightbox-text-truncated">
                  {"\n\n"}
                  [Preview truncated to {Math.round(TEXT_PREVIEW_MAX_BYTES / 1024)} KB.
                  Download to see the full file.]
                </span>
              )}
            </pre>
          )}

          {kind === "binary" && (
            <div className="lightbox-no-preview">
              <p>No inline preview available for this file type.</p>
              <a
                href={url}
                download={item.name}
                className="lightbox-download-link"
              >
                Download {item.name}
              </a>
            </div>
          )}
        </div>

        {hasSiblings && (
          <>
            <button
              type="button"
              className="lightbox-nav lightbox-nav-prev"
              onClick={prev}
              aria-label="Previous file"
              title="Previous (←)"
            >
              <svg
                viewBox="0 0 16 16"
                width="18"
                height="18"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M10 3L5 8l5 5" />
              </svg>
            </button>
            <button
              type="button"
              className="lightbox-nav lightbox-nav-next"
              onClick={next}
              aria-label="Next file"
              title="Next (→)"
            >
              <svg
                viewBox="0 0 16 16"
                width="18"
                height="18"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 3l5 5-5 5" />
              </svg>
            </button>
            <div className="lightbox-counter" aria-live="polite">
              {index + 1} / {items.length}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
