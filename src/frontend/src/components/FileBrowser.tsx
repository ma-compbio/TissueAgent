import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { BrowseEntry } from "../types/messages";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

const IMAGE_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
]);

function isImageFile(name: string): boolean {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return false;
  return IMAGE_EXTENSIONS.has(name.slice(dot).toLowerCase());
}

/** Which on-disk root the browser is talking to. */
export type FileScope = "library" | "project";

function FileNode({
  entry,
  scope,
  projectId,
  onDelete,
  onPreviewImage,
  depth = 0,
}: {
  entry: BrowseEntry;
  scope: FileScope;
  projectId?: string;
  onDelete: () => void;
  onPreviewImage: (path: string) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(false);

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
      <div className="file-node" style={{ paddingLeft: `${depth * 1.2}rem` }}>
        <div
          className="file-row dir-row"
          onClick={() => setExpanded(!expanded)}
        >
          <span className="file-icon">{expanded ? "📂" : "📁"}</span>
          <span className="file-name">{entry.name}/</span>
        </div>
        {expanded &&
          entry.children?.map((child) => (
            <FileNode
              key={child.path}
              entry={child}
              scope={scope}
              projectId={projectId}
              onDelete={onDelete}
              onPreviewImage={onPreviewImage}
              depth={depth + 1}
            />
          ))}
      </div>
    );
  }

  const isImage = isImageFile(entry.name);

  return (
    <div className="file-node" style={{ paddingLeft: `${depth * 1.2}rem` }}>
      <div
        className={`file-row ${isImage ? "file-row-clickable" : ""}`}
        onClick={isImage ? () => onPreviewImage(entry.path) : undefined}
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
  /** Tighter layout for narrow containers (sidebar embedding): the
   *  description and the preview-pane split are dropped so the tree
   *  fills the available width. */
  compact?: boolean;
  /** One-liner explanation surfaced via an info icon next to the title.
   *  Useful in compact mode where the longer description is hidden. */
  infoText?: string;
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
}: BrowserPaneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tree, setTree] = useState<BrowseEntry[]>([]);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [paneWidth, setPaneWidth] = useState(320);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const fetchTree = useCallback(async () => {
    const qs = new URLSearchParams({ scope });
    if (projectId) qs.set("project_id", projectId);
    const res = await fetch(`${API}/api/files/browse?${qs}`);
    if (res.ok) setTree(await res.json());
    else setTree([]);
    setPreviewPath(null);
  }, [scope, projectId]);

  useEffect(() => {
    fetchTree();
  }, [fetchTree, refreshKey]);

  useLayoutEffect(() => {
    if (containerRef.current) {
      setPaneWidth(Math.round(containerRef.current.offsetWidth * 0.25));
    }
  }, []);

  const handleResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const left = containerRef.current.getBoundingClientRect().left;
      const total = containerRef.current.offsetWidth;
      const next = Math.max(160, Math.min(total * 0.65, ev.clientX - left));
      setPaneWidth(Math.round(next));
    };

    const onMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  const previewFileName = previewPath
    ? previewPath.split("/").pop() ?? previewPath
    : null;

  const previewQs = new URLSearchParams({ scope });
  if (projectId) previewQs.set("project_id", projectId);
  const previewUrl = previewPath
    ? `${API}/api/files/download/${previewPath}?${previewQs}`
    : null;

  const handleUploadClick = () => fileInputRef.current?.click();
  const handleFilesChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    if (onUpload) await onUpload(files);
    // Reset the input so re-picking the same file fires onChange again.
    e.target.value = "";
    fetchTree();
  };

  return (
    <section
      className={`file-browser-section ${compact ? "compact" : ""}`}
    >
      <header className="file-browser-section-header">
        <div className="file-browser-section-titles">
          <div className="file-browser-section-title-row">
            <h2 className="file-browser-section-title">{title}</h2>
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
              <button
                className="file-browser-upload-btn"
                onClick={handleUploadClick}
                title={`Upload to ${title}`}
              >
                {compact ? "+" : "+ Upload"}
              </button>
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

      {compact ? (
        // Sidebar embedding: single-column tree, no preview, no split.
        // The user can still open files via the row's download button;
        // image previews would be too cramped in a narrow column.
        <div className="file-tree compact-tree">
          {tree.length === 0 ? (
            <div className="empty-tree">{emptyMessage ?? "No files yet."}</div>
          ) : (
            tree.map((entry) => (
              <FileNode
                key={entry.path}
                entry={entry}
                scope={scope}
                projectId={projectId}
                onDelete={fetchTree}
                onPreviewImage={setPreviewPath}
              />
            ))
          )}
        </div>
      ) : (
        <div className="file-browser-split" ref={containerRef}>
          <div className="file-browser-pane" style={{ width: paneWidth }}>
            <div className="file-tree">
              {tree.length === 0 ? (
                <div className="empty-tree">{emptyMessage ?? "No files yet."}</div>
              ) : (
                tree.map((entry) => (
                  <FileNode
                    key={entry.path}
                    entry={entry}
                    scope={scope}
                    projectId={projectId}
                    onDelete={fetchTree}
                    onPreviewImage={setPreviewPath}
                  />
                ))
              )}
            </div>
          </div>

          <div
            className="file-browser-resize-handle"
            onMouseDown={handleResizeMouseDown}
            aria-hidden="true"
          />

          {previewUrl && previewFileName && (
            <div className="file-preview-pane">
              <div className="file-preview-pane-header">
                <span className="image-preview-name">{previewFileName}</span>
                <button
                  className="file-action"
                  onClick={() => window.open(previewUrl, "_blank")}
                  title="Download"
                >
                  ⬇
                </button>
                <button
                  className="file-preview-close-btn"
                  onClick={() => setPreviewPath(null)}
                  title="Close preview"
                  aria-label="Close preview"
                >
                  ✕
                </button>
              </div>
              <div className="file-preview-pane-body">
                <img
                  src={previewUrl}
                  alt={previewFileName}
                  className="image-preview-img"
                />
              </div>
            </div>
          )}
        </div>
      )}
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
  /** Compact rendering for narrow sidebar embedding. Default is the
   *  full-width Files page layout. */
  compact?: boolean;
}

export default function FileBrowser({
  refreshKey,
  currentProjectId,
  currentProjectTitle,
  onUploadToLibrary,
  compact = false,
}: FileBrowserProps) {
  const projectLabel = currentProjectTitle?.trim()
    ? compact
      ? "Project files"
      : `Project files — ${currentProjectTitle}`
    : "Project files";

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
        compact={compact}
      />

      <BrowserPane
        title={projectLabel}
        description={
          currentProjectId
            ? "Files attached to this project, plus everything the agent has written. Sidebar uploads land in uploads/; agent outputs land in outputs/."
            : "Send a prompt or upload from the sidebar to start a project — its files will appear here."
        }
        infoText="Files for the active project: sidebar uploads land in uploads/, chat attachments in attachments/, agent outputs in outputs/."
        scope="project"
        projectId={currentProjectId || undefined}
        refreshKey={refreshKey}
        emptyMessage={
          currentProjectId
            ? "No project files yet."
            : "No active project."
        }
        compact={compact}
      />
    </div>
  );
}
