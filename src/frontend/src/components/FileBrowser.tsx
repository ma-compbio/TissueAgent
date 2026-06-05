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

function FileNode({
  entry,
  scope,
  projectId,
  onDelete,
  onPreviewFile,
  depth = 0,
}: {
  entry: BrowseEntry;
  scope: FileScope;
  projectId?: string;
  onDelete: () => void;
  onPreviewFile: (path: string) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(true);

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
              onPreviewFile={onPreviewFile}
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
}: BrowserPaneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tree, setTree] = useState<BrowseEntry[]>([]);

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

  const handleOpenPreview = useCallback(
    (path: string) => {
      const leaves = collectLeafFiles(tree);
      const items: PreviewItem[] = leaves.map((leaf) => ({
        path: leaf.path,
        name: leaf.name,
        scope,
        projectId,
      }));
      const idx = items.findIndex((it) => it.path === path);
      if (idx >= 0) onOpenPreview(items, idx);
    },
    [tree, scope, projectId, onOpenPreview],
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

      <div className={`file-tree ${compact ? "compact-tree" : ""}`}>
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
              onPreviewFile={handleOpenPreview}
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
        onOpenPreview={openPreview}
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
        onOpenPreview={openPreview}
      />

      {previewOpen && (
        <FilePreviewLightbox
          items={previewItems}
          index={previewIndex}
          onClose={closePreview}
          onIndexChange={setPreviewIndex}
        />
      )}
    </div>
  );
}
