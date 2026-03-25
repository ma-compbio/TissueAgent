import { useRef } from "react";
import type { FileInfo } from "../types/messages";

interface Props {
  pendingImages: FileInfo[];
  uploadedPdfs: FileInfo[];
  onUploadDataset: (files: FileList) => void;
  onUploadImages: (files: FileList) => void;
  onUploadPdfs: (files: FileList) => void;
}

function UploadZone({
  label,
  caption,
  accept,
  multiple,
  onFiles,
}: {
  label: string;
  caption: string;
  accept: string;
  multiple?: boolean;
  onFiles: (files: FileList) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
  };

  return (
    <div className="upload-zone">
      <div className="upload-label">{label}</div>
      <div className="upload-caption">{caption}</div>
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
        accept={accept}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files?.length) onFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}

export default function FileUpload({
  pendingImages,
  uploadedPdfs,
  onUploadDataset,
  onUploadImages,
  onUploadPdfs,
}: Props) {
  return (
    <div className="file-upload-section">
      <UploadZone
        label="Upload Dataset"
        caption="Upload dataset files for the agent to analyze."
        accept="*"
        multiple
        onFiles={onUploadDataset}
      />

      <div className="upload-divider" />

      <UploadZone
        label="Attach Images"
        caption="Attach image(s) to send with your next message."
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        onFiles={onUploadImages}
      />
      {pendingImages.length > 0 && (
        <div className="pending-files">
          Pending: {pendingImages.map((f) => f.name).join(", ")}
        </div>
      )}
      {pendingImages.length === 0 && (
        <div className="no-files">No images attached yet.</div>
      )}

      <div className="upload-divider" />

      <UploadZone
        label="Upload PDFs"
        caption="Upload PDF document(s) for the agent to reference."
        accept="application/pdf"
        multiple
        onFiles={onUploadPdfs}
      />
      {uploadedPdfs.length > 0 && (
        <div className="pending-files">
          {uploadedPdfs.map((f) => (
            <div key={f.name} className="pdf-status">
              {f.file_id ? "✅" : "⏳"} {f.name}
              {f.file_id && (
                <span className="file-id-preview">
                  {" "}
                  ({f.file_id.slice(0, 12)}...)
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {uploadedPdfs.length === 0 && (
        <div className="no-files">No PDFs uploaded yet.</div>
      )}
    </div>
  );
}
