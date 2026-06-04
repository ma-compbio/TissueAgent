import type { SessionInfo } from "../types/messages";
import FileBrowser from "./FileBrowser";
import ProjectsPanel from "./ProjectsPanel";
import Splitter from "./Splitter";
import { usePersistedSize } from "../hooks/usePersistedSize";

// Height of the Projects panel inside the sidebar (the Files panel
// fills whatever's left). Persisted across reloads. Below ~140 the
// Projects list gets too cramped to read; above ~900 the Files panel
// loses too much room on shorter laptop screens.
const PROJECTS_HEIGHT_KEY = "tissueagent:sidebar-projects-height";
const PROJECTS_HEIGHT_DEFAULT = 280;
const PROJECTS_HEIGHT_MIN = 140;
const PROJECTS_HEIGHT_MAX = 900;

interface Props {
  /** Outer sidebar width in pixels; driven by the splitter in App.tsx. */
  width: number;
  sessions: SessionInfo[];
  currentProjectId: string;
  currentProjectTitle: string;
  onFetchSessions: () => void;
  onNewProject: () => Promise<true | string>;
  onLoad: (filename: string) => Promise<boolean>;
  onDelete: (filename: string) => Promise<true | string>;
  hasMessages: boolean;
  fileBrowserRefreshKey: number;
  onUploadToLibrary: (files: FileList) => Promise<void> | void;
}

/**
 * Left column of the 3-column chat layout.
 *
 * Vertical stack: ``ProjectsPanel`` on top (resizable height), then the
 * embedded compact ``FileBrowser`` below. The plan panel used to live
 * here too but moved out to its own right-hand ``PlanColumn``.
 */
export default function Sidebar({
  width,
  sessions,
  currentProjectId,
  currentProjectTitle,
  onFetchSessions,
  onNewProject,
  onLoad,
  onDelete,
  hasMessages,
  fileBrowserRefreshKey,
  onUploadToLibrary,
}: Props) {
  const [projectsHeight, resizeProjects] = usePersistedSize(
    PROJECTS_HEIGHT_KEY,
    PROJECTS_HEIGHT_DEFAULT,
    PROJECTS_HEIGHT_MIN,
    PROJECTS_HEIGHT_MAX,
  );

  return (
    <aside
      className="sidebar"
      style={{ width: `${width}px`, minWidth: `${width}px` }}
    >
      <div
        className="sidebar-projects"
        style={{ height: `${projectsHeight}px` }}
      >
        <ProjectsPanel
          sessions={sessions}
          currentProjectId={currentProjectId}
          hasMessages={hasMessages}
          onFetchSessions={onFetchSessions}
          onNewProject={onNewProject}
          onLoad={onLoad}
          onDelete={onDelete}
        />
      </div>

      <Splitter
        orientation="horizontal"
        onResize={resizeProjects}
        ariaLabel="Resize projects panel"
      />

      <div className="sidebar-files">
        <FileBrowser
          refreshKey={fileBrowserRefreshKey}
          currentProjectId={currentProjectId}
          currentProjectTitle={currentProjectTitle}
          onUploadToLibrary={onUploadToLibrary}
          compact
        />
      </div>
    </aside>
  );
}
