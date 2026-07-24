import { useCallback, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { BrowseEntry, SkillDetail } from "../types/messages";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

/** Read-only view of the skills loaded into a trace step's sub-agent.
 *  Each skill expands to reveal its full markdown; folder skills also list
 *  their bundled files, previewable inline. */
export default function TraceSkills({ skills }: { skills: string[] }) {
  if (!skills.length) return null;
  return (
    <div className="trace-skills">
      <span className="trace-step-label">
        skills loaded ({skills.length})
      </span>
      <div className="trace-skills-list">
        {skills.map((name) => (
          <SkillRow key={name} name={name} />
        ))}
      </div>
    </div>
  );
}

function SkillRow({ name }: { name: string }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Lazy-fetch on first expand so a step with many skills doesn't fire a
  // request per skill up front.
  const load = useCallback(() => {
    if (detail || loading) return;
    setLoading(true);
    setError(null);
    fetch(`${API}/api/skills/${encodeURIComponent(name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Skill unavailable (${r.status})`);
        return r.json() as Promise<SkillDetail>;
      })
      .then((data) => setDetail(data))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load skill"))
      .finally(() => setLoading(false));
  }, [detail, loading, name]);

  const toggle = () => {
    setOpen((o) => !o);
    if (!open) load();
  };

  return (
    <div className="skill-row">
      <button className="skill-row-header" onClick={toggle} aria-expanded={open}>
        <span className="trace-expand-icon">{open ? "▼" : "▶"}</span>
        <span className="skill-row-name">{name}</span>
        {detail?.is_dir && <span className="skill-row-badge">folder</span>}
      </button>
      {open && (
        <div className="skill-row-body">
          {loading && <div className="skill-loading">Loading…</div>}
          {error && <div className="skill-error">{error}</div>}
          {detail && <SkillBody name={name} detail={detail} />}
        </div>
      )}
    </div>
  );
}

function SkillBody({ name, detail }: { name: string; detail: SkillDetail }) {
  return (
    <>
      {detail.description && (
        <p className="skill-description">{detail.description}</p>
      )}
      <div className="skill-content markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{detail.content}</ReactMarkdown>
      </div>
      {detail.is_dir && detail.dir_path && (
        <div className="skill-files">
          <span className="trace-step-label">skill files</span>
          <code className="skill-dir-path">{detail.dir_path}/</code>
          <FileTree
            skillName={name}
            entries={detail.files ?? []}
            mainFile={detail.main_file}
          />
        </div>
      )}
    </>
  );
}

/** Render the bundled file tree; leaf text files expand to an inline preview. */
function FileTree({
  skillName,
  entries,
  mainFile,
  depth = 0,
}: {
  skillName: string;
  entries: BrowseEntry[];
  mainFile?: string;
  depth?: number;
}) {
  return (
    <ul className="skill-file-tree" style={{ paddingLeft: depth ? "1rem" : 0 }}>
      {entries.map((entry) =>
        entry.is_dir ? (
          <li key={entry.path} className="skill-file-dir">
            <span className="skill-file-dirname">{entry.name}/</span>
            <FileTree
              skillName={skillName}
              entries={entry.children ?? []}
              mainFile={mainFile}
              depth={depth + 1}
            />
          </li>
        ) : (
          <SkillFile
            key={entry.path}
            skillName={skillName}
            entry={entry}
            isMain={entry.path === mainFile}
          />
        ),
      )}
    </ul>
  );
}

function SkillFile({
  skillName,
  entry,
  isMain,
}: {
  skillName: string;
  entry: BrowseEntry;
  isMain: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    if (content !== null || loading) return;
    setLoading(true);
    setError(null);
    fetch(
      `${API}/api/skills/${encodeURIComponent(skillName)}/file?path=${encodeURIComponent(
        entry.path,
      )}`,
    )
      .then(async (r) => {
        if (!r.ok) {
          const detail = await r.json().catch(() => null);
          throw new Error(detail?.detail || `Cannot preview (${r.status})`);
        }
        return r.json() as Promise<{ content: string }>;
      })
      .then((data) => setContent(data.content))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load file"))
      .finally(() => setLoading(false));
  }, [content, loading, skillName, entry.path]);

  const toggle = () => {
    setOpen((o) => !o);
    if (!open) load();
  };

  return (
    <li className="skill-file">
      <button className="skill-file-header" onClick={toggle} aria-expanded={open}>
        <span className="trace-expand-icon">{open ? "▾" : "▸"}</span>
        <span className="skill-file-name">{entry.name}</span>
        {isMain && <span className="skill-file-tag">skill</span>}
      </button>
      {open && (
        <div className="skill-file-preview">
          {loading && <div className="skill-loading">Loading…</div>}
          {error && <div className="skill-error">{error}</div>}
          {content !== null && <pre className="skill-file-content">{content}</pre>}
        </div>
      )}
    </li>
  );
}
