import { useCallback, useEffect, useState } from "react";
import type { BrowseEntry } from "../types/messages";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

function FileNode({
  entry,
  onDelete,
  depth = 0,
}: {
  entry: BrowseEntry;
  onDelete: () => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(false);

  const handleDownload = () => {
    window.open(`${API}/api/files/download/${entry.path}`, "_blank");
  };

  const handleDelete = async () => {
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
              depth={depth + 1}
            />
          ))}
      </div>
    );
  }

  return (
    <div className="file-node" style={{ paddingLeft: `${depth * 1.2}rem` }}>
      <div className="file-row">
        <span className="file-icon">📄</span>
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

export default function FileBrowser() {
  const [tree, setTree] = useState<BrowseEntry[]>([]);

  const fetchTree = useCallback(async () => {
    const res = await fetch(`${API}/api/files/browse`);
    if (res.ok) setTree(await res.json());
  }, []);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  return (
    <div className="file-browser">
      <div className="file-browser-header">
        <h3>File Browser</h3>
        <button className="refresh-btn" onClick={fetchTree}>
          ↻ Refresh
        </button>
      </div>
      <div className="file-tree">
        {tree.length === 0 ? (
          <div className="empty-tree">No files yet.</div>
        ) : (
          tree.map((entry) => (
            <FileNode key={entry.path} entry={entry} onDelete={fetchTree} />
          ))
        )}
      </div>
    </div>
  );
}
