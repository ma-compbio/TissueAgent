import { useCallback, useState } from "react";
import type { FileInfo, SessionInfo } from "../types/messages";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export function useSession() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<FileInfo[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string>("");

  const fetchSessions = useCallback(async () => {
    const res = await fetch(`${API}/api/sessions/list`);
    if (res.ok) setSessions(await res.json());
  }, []);

  const fetchCurrentProject = useCallback(async () => {
    const res = await fetch(`${API}/api/sessions/current`);
    if (res.ok) {
      const data = await res.json();
      setCurrentProjectId(data.project_id || "");
    }
  }, []);

  const saveSession = useCallback(async (): Promise<true | string> => {
    const res = await fetch(`${API}/api/sessions/save`, { method: "POST" });
    if (res.ok) {
      await fetchSessions();
      return true;
    }
    // Surface the server's detail so the user knows *why*. e.g. 409
    // when a run is in progress, 400 when there's nothing to save.
    try {
      const body = await res.json();
      return typeof body?.detail === "string" ? body.detail : "Failed to save.";
    } catch {
      return "Failed to save.";
    }
  }, [fetchSessions]);

  const loadSession = useCallback(async (filename: string) => {
    const res = await fetch(
      `${API}/api/sessions/load?filename=${encodeURIComponent(filename)}`,
      { method: "POST" }
    );
    return res.ok;
  }, []);

  const _download = useCallback(
    async (path: string, fallbackName: string) => {
      const res = await fetch(`${API}${path}`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download =
        res.headers
          .get("content-disposition")
          ?.match(/filename="(.+)"/)?.[1] ?? fallbackName;
      // Firefox refuses to trigger a download unless the anchor is in the
      // DOM. Attach → click → detach, and revoke the object URL *after*
      // a tick so the download start doesn't race the revoke on some
      // browsers (Safari in particular).
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    [],
  );

  const exportHtml = useCallback(
    () => _download("/api/sessions/export/html", "session.html"),
    [_download],
  );

  const exportMarkdown = useCallback(
    () => _download("/api/sessions/export/markdown", "session.md"),
    [_download],
  );

  const clearSession = useCallback(async (): Promise<true | string> => {
    const res = await fetch(`${API}/api/sessions/clear`, { method: "POST" });
    if (res.ok) {
      // Clear the locally-tracked file list too; uploaded files
      // metadata is gone server-side now.
      setUploadedFiles([]);
      setCurrentProjectId("");
      return true;
    }
    try {
      const body = await res.json();
      return typeof body?.detail === "string" ? body.detail : "Failed to clear.";
    } catch {
      return "Failed to clear.";
    }
  }, []);

  const deleteSession = useCallback(
    async (filename: string): Promise<true | string> => {
      const res = await fetch(
        `${API}/api/sessions/${encodeURIComponent(filename)}`,
        { method: "DELETE" },
      );
      if (res.ok) {
        await fetchSessions();
        return true;
      }
      try {
        const body = await res.json();
        return typeof body?.detail === "string" ? body.detail : "Failed to delete.";
      } catch {
        return "Failed to delete.";
      }
    },
    [fetchSessions],
  );

  const uploadFiles = useCallback(
    async (
      files: FileList,
      target: "project" | "library" = "project",
    ): Promise<true | string> => {
      const form = new FormData();
      for (const f of files) form.append("files", f);
      let res: Response;
      try {
        res = await fetch(`${API}/api/files/upload?target=${target}`, {
          method: "POST",
          body: form,
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        const detail = `Upload failed: ${msg}`;
        // eslint-disable-next-line no-alert
        alert(detail);
        return detail;
      }
      if (!res.ok) {
        let detail = `Upload failed (HTTP ${res.status}).`;
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
        } catch {
          // Server didn't return JSON; keep the generic message.
        }
        // eslint-disable-next-line no-alert
        alert(detail);
        return detail;
      }
      const data = await res.json();
      // Only project uploads bind to the current conversation; library
      // uploads are persistent references not tied to any chat turn.
      if (target === "project") {
        setUploadedFiles((prev) => [...prev, ...data.files]);
      }
      return true;
    },
    [],
  );

  return {
    sessions,
    uploadedFiles,
    currentProjectId,
    setCurrentProjectId,
    fetchSessions,
    fetchCurrentProject,
    saveSession,
    loadSession,
    clearSession,
    exportHtml,
    exportMarkdown,
    deleteSession,
    uploadFiles,
  };
}
