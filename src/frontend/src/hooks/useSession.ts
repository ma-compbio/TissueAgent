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

  const saveSession = useCallback(async () => {
    const res = await fetch(`${API}/api/sessions/save`, { method: "POST" });
    if (res.ok) {
      await fetchSessions();
      return true;
    }
    return false;
  }, [fetchSessions]);

  const loadSession = useCallback(async (filename: string) => {
    const res = await fetch(
      `${API}/api/sessions/load?filename=${encodeURIComponent(filename)}`,
      { method: "POST" }
    );
    return res.ok;
  }, []);

  const exportHtml = useCallback(async () => {
    const res = await fetch(`${API}/api/sessions/export/html`);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download =
      res.headers.get("content-disposition")?.match(/filename="(.+)"/)?.[1] ??
      "session.html";
    a.click();
    URL.revokeObjectURL(url);
  }, []);

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
    uploadFiles,
  };
}
