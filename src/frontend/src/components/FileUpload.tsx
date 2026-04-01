import { useRef } from "react";
import type { FileInfo } from "../types/messages";

interface Props {
  uploadedFiles: FileInfo[];
  onUploadFiles: (files: FileList) => void;
}

const CATEGORY_ICONS: Record<string, string> = {
  dataset: "📊",
  image: "🖼️",
  pdf: "📄",
  general: "📎",
};

export default function FileUpload({ uploadedFiles, onUploadFiles }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) onUploadFiles(e.dataTransfer.files);
  };

  return (
    <div className="file-upload-section">
      <div className="upload-label">Upload Files</div>
      <div className="upload-caption">
        Dataset files (h5ad, csv, etc.) go to dataset/. Everything else goes to
        uploads/.
      </div>
      <div
        className="drop-area"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        Drop files or click to browse
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files?.length) onUploadFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {uploadedFiles.length > 0 && (
        <div className="uploaded-file-list">
          {uploadedFiles.map((f, i) => (
            <div key={`${f.name}-${i}`} className="uploaded-file-row">
              <span>{CATEGORY_ICONS[f.category ?? "general"]}</span>
              <span className="uploaded-file-name">{f.name}</span>
              <span className="uploaded-file-cat">{f.category ?? "general"}</span>
            </div>
          ))}
        </div>
      )}
      {uploadedFiles.length === 0 && (
        <div className="no-files">No files uploaded yet.</div>
      )}
    </div>
  );
}
