/**
 * Projects panel — persistent list of saved chat sessions.
 *
 * Replaces the older SessionManager. Each row is one project (a saved
 * conversation file on disk). The active project is highlighted.
 *
 * Auto-save lives on the server: the first user prompt mints a project
 * id and writes a file; subsequent saves overwrite the same file in
 * place. The panel just lists what's on disk.
 */

import { useEffect } from "react";
import type { SessionInfo } from "../types/messages";

interface Props {
  sessions: SessionInfo[];
  currentProjectId: string;
  hasMessages: boolean;
  onFetchSessions: () => void;
  onNewProject: () => Promise<true | string>;
  onLoad: (filename: string) => Promise<boolean>;
  onDelete: (filename: string) => Promise<true | string>;
}

export default function ProjectsPanel({
  sessions,
  currentProjectId,
  hasMessages,
  onFetchSessions,
  onNewProject,
  onLoad,
  onDelete,
}: Props) {
  useEffect(() => {
    onFetchSessions();
  }, [onFetchSessions]);

  const handleNew = async () => {
    if (hasMessages) {
      const confirmed = window.confirm(
        "Start a new project? The current conversation will be cleared from view " +
          "(it's already saved as a project below).",
      );
      if (!confirmed) return;
    }
    await onNewProject();
  };

  const handleDelete = async (e: React.MouseEvent, filename: string) => {
    e.stopPropagation();
    const confirmed = window.confirm(
      "Delete this project? This cannot be undone.",
    );
    if (!confirmed) return;
    await onDelete(filename);
  };

  return (
    <section className="projects-panel" aria-label="Projects">
      <header className="projects-header">
        <h2 className="sidebar-section-title">Projects</h2>
        <div className="projects-header-actions">
          <button
            type="button"
            className="section-icon-btn"
            onClick={handleNew}
            aria-label="Start a new project"
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
              Start a new project
            </span>
          </button>
          <button
            type="button"
            className="section-icon-btn"
            onClick={() => onFetchSessions()}
            aria-label="Refresh project list"
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
              strokeLinejoin="round"
            >
              <path d="M13.2 7.5a5.2 5.2 0 1 1-1.6-3.7" />
              <path d="M13.5 2.2v3.5h-3.5" />
            </svg>
            <span className="section-icon-tooltip" role="tooltip">
              Refresh
            </span>
          </button>
        </div>
      </header>

      <ul className="projects-list" role="list">
        {sessions.length === 0 && (
          <li className="projects-empty">
            <span className="projects-empty-title">No projects yet</span>
            <span className="projects-empty-body">
              Send a prompt to start your first project.
            </span>
          </li>
        )}

        {sessions.map((s) => {
          const projectId = s.project_id ?? s.filename;
          const isActive = projectId === currentProjectId;
          const displayTitle = s.title?.trim() || "Untitled project";
          const displayTime = s.saved_at?.trim() || s.label;
          return (
            <li key={s.filename}>
              <button
                type="button"
                className={`project-row ${isActive ? "active" : ""}`}
                onClick={() => onLoad(s.filename)}
                aria-current={isActive ? "true" : undefined}
              >
                <span className="project-row-title" title={displayTitle}>
                  {displayTitle}
                </span>
                <span className="project-row-meta">
                  <span className="project-row-time">{displayTime}</span>
                  <span
                    className="project-row-delete"
                    role="button"
                    aria-label="Delete project"
                    tabIndex={0}
                    onClick={(e) => handleDelete(e, s.filename)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        e.stopPropagation();
                        handleDelete(
                          e as unknown as React.MouseEvent,
                          s.filename,
                        );
                      }
                    }}
                  >
                    <svg
                      viewBox="0 0 16 16"
                      width="12"
                      height="12"
                      aria-hidden="true"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                    >
                      <path d="M3 4h10M6.5 4V2.5h3V4M5 4l.5 9h5L11 4M7 6.5v4M9 6.5v4" />
                    </svg>
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
