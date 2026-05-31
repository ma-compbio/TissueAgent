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

function FileNode({
  entry,
  onDelete,
  onPreviewImage,
  depth = 0,
}: {
  entry: BrowseEntry;
  onDelete: () => void;
  onPreviewImage: (path: string) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(false);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    window.open(`${API}/api/files/download/${entry.path}`, "_blank");
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete ${entry.name}?`)) return;
    const res = await fetch(`${API}/api/files/${entry.path}`, {
      method: "DELETE",
    });
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

export default function FileBrowser({ refreshKey }: { refreshKey?: number }) {
  const [tree, setTree] = useState<BrowseEntry[]>([]);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [paneWidth, setPaneWidth] = useState(320);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const fetchTree = useCallback(async () => {
    const res = await fetch(`${API}/api/files/browse`);
    if (res.ok) setTree(await res.json());
  }, []);

  useEffect(() => {
    fetchTree();
  }, [fetchTree, refreshKey]);

  // Initialize pane width to ~25% of the container on first render.
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

  const previewFileName = previewPath ? (previewPath.split("/").pop() ?? previewPath) : null;

  return (
    <div className="file-browser-split" ref={containerRef}>
      <div className="file-browser-pane" style={{ width: paneWidth }}>
        <div className="file-browser-pane-header">
          <span className="file-browser-pane-title">Output Files</span>
          <button
            className="file-browser-refresh-btn"
            onClick={fetchTree}
            title="Refresh"
            aria-label="Refresh file list"
          >
            ↻
          </button>
        </div>
        <div className="file-tree">
          {tree.length === 0 ? (
            <div className="empty-tree">No files yet.</div>
          ) : (
            tree.map((entry) => (
              <FileNode
                key={entry.path}
                entry={entry}
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

      {previewPath && previewFileName && (
        <div className="file-preview-pane">
          <div className="file-preview-pane-header">
            <span className="image-preview-name">{previewFileName}</span>
            <button
              className="file-action"
              onClick={() =>
                window.open(`${API}/api/files/download/${previewPath}`, "_blank")
              }
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
              src={`${API}/api/files/download/${previewPath}`}
              alt={previewFileName}
              className="image-preview-img"
            />
          </div>
        </div>
      )}
    </div>
  );
}
