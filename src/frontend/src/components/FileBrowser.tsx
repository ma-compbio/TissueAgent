import { useCallback, useEffect, useRef, useState } from "react";
import type { BrowseEntry } from "../types/messages";
import FilePreviewLightbox, {
  type PreviewItem,
} from "./FilePreviewLightbox";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

const IMAGE_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".tif", ".tiff",
]);

function fileExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

function isImageFile(name: string): boolean {
  return IMAGE_EXTENSIONS.has(fileExt(name));
}

/** Which on-disk root the browser is talking to. */
export type FileScope = "library" | "project";

/** Flatten a BrowseEntry tree into a list of leaf files, in render order.
 *  Used by FilePreviewLightbox so prev/next can walk siblings naturally. */
function collectLeafFiles(entries: BrowseEntry[]): BrowseEntry[] {
  const out: BrowseEntry[] = [];
  const walk = (es: BrowseEntry[]) => {
    for (const e of es) {
      if (e.is_dir) walk(e.children ?? []);
      else out.push(e);
    }
  };
  walk(entries);
  return out;
}

/** Walk the tree to *path* (a "a/b/c"-style relative path) and return the
 *  entries that live there. Returns null when the path doesn't resolve
 *  to a directory in the current tree (e.g. it was removed). Empty path
 *  is the root. */
function entriesAt(
  tree: BrowseEntry[],
  path: string,
): BrowseEntry[] | null {
  if (!path) return tree;
  const parts = path.split("/").filter(Boolean);
  let level: BrowseEntry[] = tree;
  for (const part of parts) {
    const next: BrowseEntry | undefined = level.find(
      (e) => e.is_dir && e.name === part,
    );
    if (!next) return null;
    level = next.children ?? [];
  }
  return level;
}

/** Split a path into [{ name, path }] segments for breadcrumb rendering. */
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

/** Drop the trailing segment from a path. ``"a/b/c"`` → ``"a/b"``;
 *  ``"a"`` or ``""`` → ``""``. */
function parentPath(path: string): string {
  if (!path) return "";
  const parts = path.split("/").filter(Boolean);
  parts.pop();
  return parts.join("/");
}

function FileNode({
  entry,
  scope,
  projectId,
  onDelete,
  onPreviewFile,
  onEnterDir,
}: {
  entry: BrowseEntry;
  scope: FileScope;
  projectId?: string;
  onDelete: () => void;
  onPreviewFile: (path: string) => void;
  onEnterDir: (path: string) => void;
}) {
  const qs = new URLSearchParams({ scope });
  if (projectId) qs.set("project_id", projectId);
  const downloadUrl = `${API}/api/files/download/${entry.path}?${qs}`;
  const deleteUrl = `${API}/api/files/${entry.path}?${qs}`;

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    window.open(downloadUrl, "_blank");
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete ${entry.name}?`)) return;
    const res = await fetch(deleteUrl, { method: "DELETE" });
    if (res.ok) onDelete();
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (entry.is_dir) {
    return (
      <div className="file-node">
        <div
          className="file-row dir-row file-row-clickable"
          onClick={() => onEnterDir(entry.path)}
          title={`Open ${entry.name}/`}
        >
          <span className="file-icon">📁</span>
          <span className="file-name">{entry.name}/</span>
          <span className="file-row-chevron" aria-hidden="true">›</span>
        </div>
      </div>
    );
  }

  const isImage = isImageFile(entry.name);

  return (
    <div className="file-node">
      <div
        className="file-row file-row-clickable"
        onClick={() => onPreviewFile(entry.path)}
        title="Open preview"
      >
        <span className="file-icon">{isImage ? "🖼" : "📄"}</span>
        <span className="file-name">{entry.name}</span>
        <span className="file-size">{formatSize(entry.size)}</span>
        <button className="file-action" onClick={handleDownload} title="Download">
          ⬇
        </button>
        <button className="file-action delete" onClick={handleDelete} title="Delete">
          ✕
        </button>
      </div>
    </div>
  );
}

interface BrowserPaneProps {
  title: string;
  description?: string;
  scope: FileScope;
  projectId?: string;
  refreshKey?: number;
  emptyMessage?: string;
  /** When true, render an "Upload" button in the section header. */
  uploadable?: boolean;
  /** Required when ``uploadable``. Called with the chosen files. */
  onUpload?: (files: FileList) => Promise<void> | void;
  /** Hover/focus tooltip text for the upload button. */
  uploadTooltip?: string;
  /** Tighter layout for narrow containers (sidebar embedding): the
   *  description block is hidden, the upload-button label is collapsed
   *  to "+", and the tree fills the column. */
  compact?: boolean;
  /** One-liner explanation surfaced via an info icon next to the title.
   *  Useful in compact mode where the longer description is hidden. */
  infoText?: string;
  /** Open the parent-owned lightbox preview. The pane converts its
   *  current tree's leaf files into PreviewItem[] and tells the parent
   *  which one to focus. */
  onOpenPreview: (items: PreviewItem[], index: number) => void;
  /** Subtle status pill shown next to the title (e.g. "Unsaved"). */
  statusBadge?: string;
  /** Controlled current path. When provided, the pane reads from this
   *  instead of its own internal state. Pair with ``onPathChange``. */
  currentPath?: string;
  /** Notified whenever the pane wants to change its path (folder
   *  click, breadcrumb click, up arrow). Required when ``currentPath``
   *  is provided. */
  onPathChange?: (next: string) => void;
}

function BrowserPane({
  title,
  description,
  scope,
  projectId,
  refreshKey,
  emptyMessage,
  uploadable,
  onUpload,
  compact = false,
  infoText,
  onOpenPreview,
  statusBadge,
  currentPath: controlledPath,
  onPathChange,
  uploadTooltip,
}: BrowserPaneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tree, setTree] = useState<BrowseEntry[]>([]);
  // Current folder path *within* this pane's tree. Empty string = root.
  // When ``currentPath`` is passed as a prop the pane is controlled by
  // the parent (so the lightbox can drive navigation); otherwise it
  // owns its own state internally.
  const [uncontrolledPath, setUncontrolledPath] = useState<string>("");
  const isControlled = controlledPath !== undefined;
  const currentPath = isControlled ? controlledPath : uncontrolledPath;
  const setCurrentPath = useCallback(
    (next: string) => {
      if (isControlled) {
        onPathChange?.(next);
      } else {
        setUncontrolledPath(next);
      }
    },
    [isControlled, onPathChange],
  );

  const fetchTree = useCallback(async () => {
    const qs = new URLSearchParams({ scope });
    if (projectId) qs.set("project_id", projectId);
    const res = await fetch(`${API}/api/files/browse?${qs}`);
    if (res.ok) setTree(await res.json());
    else setTree([]);
  }, [scope, projectId]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree, refreshKey]);

  // Tree root identity changed (e.g. user switched projects). Drop the
  // path so we don't display contents from the previous project. Only
  // applies in uncontrolled mode — the parent owns reset behavior when
  // it's driving currentPath.
  useEffect(() => {
    if (!isControlled) setUncontrolledPath("");
  }, [scope, projectId, isControlled]);

  // After a refetch, if the currentPath no longer resolves (folder was
  // deleted, project switched, …) fall back to the deepest ancestor
  // that still does — or root.
  useEffect(() => {
    if (!currentPath) return;
    if (entriesAt(tree, currentPath) !== null) return;
    let p = parentPath(currentPath);
    while (p && entriesAt(tree, p) === null) p = parentPath(p);
    setCurrentPath(p);
  }, [tree, currentPath, setCurrentPath]);

  const visibleEntries = entriesAt(tree, currentPath) ?? [];

  const handleOpenPreview = useCallback(
    (path: string) => {
      // Walk only the current folder for prev/next siblings — feels
      // natural; "next" from a project output shouldn't jump up into
      // attachments/ and back down.
      const leaves = collectLeafFiles(visibleEntries);
      const items: PreviewItem[] = leaves.map((leaf) => ({
        path: leaf.path,
        name: leaf.name,
        scope,
        projectId,
      }));
      const idx = items.findIndex((it) => it.path === path);
      if (idx >= 0) onOpenPreview(items, idx);
    },
    [visibleEntries, scope, projectId, onOpenPreview],
  );

  const handleUploadClick = () => fileInputRef.current?.click();
  const handleFilesChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    if (onUpload) await onUpload(files);
    // Reset the input so re-picking the same file fires onChange again.
    e.target.value = "";
    fetchTree();
  };

  const segments = breadcrumbSegments(currentPath);
  const isAtRoot = currentPath === "";

  return (
    <section
      className={`file-browser-section ${compact ? "compact" : ""}`}
    >
      <header className="file-browser-section-header">
        <div className="file-browser-section-titles">
          <div className="file-browser-section-title-row">
            <h2 className="file-browser-section-title">{title}</h2>
            {statusBadge && (
              <span
                className="file-browser-section-badge"
                title={statusBadge}
              >
                {statusBadge}
              </span>
            )}
            {infoText && (
              <span
                className="file-browser-info"
                tabIndex={0}
                aria-label={`About ${title}`}
                role="note"
              >
                <svg
                  viewBox="0 0 16 16"
                  width="13"
                  height="13"
                  aria-hidden="true"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.4"
                >
                  <circle cx="8" cy="8" r="6.5" />
                  <line x1="8" y1="7" x2="8" y2="11.5" strokeLinecap="round" />
                  <circle cx="8" cy="4.7" r="0.6" fill="currentColor" stroke="none" />
                </svg>
                <span className="file-browser-info-popover" role="tooltip">
                  {infoText}
                </span>
              </span>
            )}
          </div>
          {description && !compact && (
            <p className="file-browser-section-desc">{description}</p>
          )}
        </div>
        <div className="file-browser-section-actions">
          {uploadable && (
            <>
              {compact ? (
                <button
                  type="button"
                  className="section-icon-btn"
                  onClick={handleUploadClick}
                  aria-label={uploadTooltip ?? `Upload to ${title}`}
                >
                  <svg
                    viewBox="0 0 16 16"
                    width="14"
                    height="14"
                    aria-hidden="true"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  >
                    <path d="M8 3v10M3 8h10" />
                  </svg>
                  <span className="section-icon-tooltip" role="tooltip">
                    {uploadTooltip ?? `Upload to ${title}`}
                  </span>
                </button>
              ) : (
                <button
                  type="button"
                  className="file-browser-upload-btn"
                  onClick={handleUploadClick}
                  title={uploadTooltip ?? `Upload to ${title}`}
                >
                  + Upload
                </button>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                hidden
                onChange={handleFilesChosen}
              />
            </>
          )}
          <button
            className="file-browser-refresh-btn"
            onClick={fetchTree}
            title="Refresh"
            aria-label={`Refresh ${title}`}
          >
            ↻
          </button>
        </div>
      </header>

      <nav className="file-browser-breadcrumb" aria-label="Current path">
        <button
          type="button"
          className="breadcrumb-up"
          onClick={() => setCurrentPath(parentPath(currentPath))}
          disabled={isAtRoot}
          aria-label="Go up one folder"
          title="Up one folder"
        >
          ↑
        </button>
        <ol className="breadcrumb-trail">
          <li>
            <button
              type="button"
              className={`breadcrumb-segment ${isAtRoot ? "active" : ""}`}
              onClick={() => setCurrentPath("")}
            >
              {title}
            </button>
          </li>
          {segments.map((seg, i) => {
            const isLast = i === segments.length - 1;
            return (
              <li key={seg.path}>
                <span className="breadcrumb-separator" aria-hidden="true">/</span>
                <button
                  type="button"
                  className={`breadcrumb-segment ${isLast ? "active" : ""}`}
                  onClick={() => setCurrentPath(seg.path)}
                >
                  {seg.name}
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className={`file-tree ${compact ? "compact-tree" : ""}`}>
        {visibleEntries.length === 0 ? (
          <div className="empty-tree">
            {isAtRoot
              ? (emptyMessage ?? "No files yet.")
              : "This folder is empty."}
          </div>
        ) : (
          visibleEntries.map((entry) => (
            <FileNode
              key={entry.path}
              entry={entry}
              scope={scope}
              projectId={projectId}
              onDelete={fetchTree}
              onPreviewFile={handleOpenPreview}
              onEnterDir={setCurrentPath}
            />
          ))
        )}
      </div>
    </section>
  );
}

interface FileBrowserProps {
  /** Frontend bumps this counter to force a refetch (e.g. after uploads). */
  refreshKey?: number;
  /** Currently-active project id, or empty string if none. */
  currentProjectId: string;
  /** Display title for the active project, used in the section header. */
  currentProjectTitle: string;
  /** Upload handler for the Library "+ Upload" button. */
  onUploadToLibrary: (files: FileList) => Promise<void> | void;
  /** Upload handler for the Project Files "+ Upload" button.
   *  Files land in projects/<active>/uploads/, minting a project if
   *  none is active (the upload becomes part of the next conversation). */
  onUploadToProject: (files: FileList) => Promise<void> | void;
  /** Compact rendering for narrow sidebar embedding. Default is the
   *  full-width Files page layout. */
  compact?: boolean;
}

export default function FileBrowser({
  refreshKey,
  currentProjectId,
  currentProjectTitle,
  onUploadToLibrary,
  onUploadToProject,
  compact = false,
}: FileBrowserProps) {
  const projectLabel = currentProjectTitle?.trim()
    ? compact
      ? "Project files"
      : `Project files — ${currentProjectTitle}`
    : "Project files";

  // Per-pane path state lives here at the root so the lightbox can
  // drive each pane's currentPath when the user clicks a breadcrumb
  // segment inside it. Each pane is still self-managed otherwise.
  const [libraryPath, setLibraryPath] = useState<string>("");
  const [projectPath, setProjectPath] = useState<string>("");

  // Reset the project pane's path whenever the active project changes
  // (the project tree's root identity has changed too).
  useEffect(() => {
    setProjectPath("");
  }, [currentProjectId]);

  // Lightbox state lives at the root so a single open preview is shared
  // across both panes — and so the lightbox unmounts cleanly when the
  // user closes it, regardless of which pane the file came from.
  const [previewItems, setPreviewItems] = useState<PreviewItem[]>([]);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);

  const openPreview = useCallback((items: PreviewItem[], index: number) => {
    if (items.length === 0 || index < 0 || index >= items.length) return;
    setPreviewItems(items);
    setPreviewIndex(index);
    setPreviewOpen(true);
  }, []);

  const closePreview = useCallback(() => setPreviewOpen(false), []);

  // Lightbox breadcrumb dispatch: close the lightbox and jump the
  // matching pane to that folder.
  const handleJumpToPath = useCallback(
    (scope: FileScope, path: string) => {
      if (scope === "library") setLibraryPath(path);
      else setProjectPath(path);
      setPreviewOpen(false);
    },
    [],
  );

  return (
    <div className={`file-browser-stack ${compact ? "compact" : ""}`}>
      <BrowserPane
        title="Library"
        description="Persistent reference data shared across every project. Use the + Upload button here to add datasets and reference files that any project can read."
        infoText="Persistent reference data shared across all projects. Use + Upload to add datasets or files any project can read."
        scope="library"
        refreshKey={refreshKey}
        emptyMessage={compact ? "No library files." : "No library files yet. Use + Upload to add datasets or reference files."}
        uploadable
        onUpload={onUploadToLibrary}
        uploadTooltip="Upload to library"
        compact={compact}
        onOpenPreview={openPreview}
        currentPath={libraryPath}
        onPathChange={setLibraryPath}
      />

      <BrowserPane
        title={projectLabel}
        description={
          currentProjectId
            ? "Files attached to this project, plus everything the agent has written. Sidebar uploads land in uploads/; agent outputs land in outputs/."
            : "Files you upload before the first prompt stay here as a temporary draft. They become part of the project (and persist) once you send a message."
        }
        infoText={
          currentProjectId
            ? "Files for the active project: sidebar uploads land in uploads/, chat attachments in attachments/, agent outputs in outputs/."
            : "Draft project — uploads will be moved into this project on first prompt. Starting a new project before then discards them."
        }
        scope="project"
        projectId={currentProjectId || undefined}
        refreshKey={refreshKey}
        emptyMessage={
          currentProjectId
            ? "No project files yet."
            : "No files staged yet. Upload to stage files for the next prompt."
        }
        compact={compact}
        onOpenPreview={openPreview}
        statusBadge={!currentProjectId ? "Unsaved" : undefined}
        currentPath={projectPath}
        onPathChange={setProjectPath}
        uploadable
        onUpload={onUploadToProject}
        uploadTooltip="Upload to project"
      />

      {previewOpen && (
        <FilePreviewLightbox
          items={previewItems}
          index={previewIndex}
          onClose={closePreview}
          onIndexChange={setPreviewIndex}
          onJumpToPath={handleJumpToPath}
        />
      )}
    </div>
  );
}
