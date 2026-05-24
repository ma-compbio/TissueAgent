import { useCallback, useState } from "react";
import type { FileInfo, SessionInfo } from "../types/messages";

const API = import.meta.env.DEV ? "http://localhost:8000" : "";

export function useSession() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<FileInfo[]>([]);

  const fetchSessions = useCallback(async () => {
    const res = await fetch(`${API}/api/sessions/list`);
    if (res.ok) setSessions(await res.json());
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
      a.click();
      URL.revokeObjectURL(url);
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

  const uploadFiles = useCallback(async (files: FileList) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const res = await fetch(`${API}/api/files/upload`, {
      method: "POST",
      body: form,
    });
    if (res.ok) {
      const data = await res.json();
      setUploadedFiles((prev) => [...prev, ...data.files]);
    }
  }, []);

  return {
    sessions,
    uploadedFiles,
    fetchSessions,
    saveSession,
    loadSession,
    exportHtml,
    exportMarkdown,
    deleteSession,
    uploadFiles,
  };
}
