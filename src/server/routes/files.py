"""REST endpoints for file management: dataset upload, image/PDF attachments, and browsing."""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import DATA_DIR, DATASET_DIR, PDF_UPLOADS_DIR, UPLOADS_DIR
from server.session_manager import session
from server.utils import next_available_path, upload_pdf_to_openai

router = APIRouter(prefix="/api/files")


class FileInfo(BaseModel):
    """Metadata for an uploaded file."""

    name: str
    path: str
    file_id: str | None = None


class BrowseEntry(BaseModel):
    """A single entry in a directory listing."""

    name: str
    path: str
    is_dir: bool
    size: int = 0
    children: list["BrowseEntry"] | None = None


# ---------------------------------------------------------------------------
# Dataset upload
# ---------------------------------------------------------------------------


@router.post("/dataset", response_model=List[FileInfo])
async def upload_dataset(files: List[UploadFile] = File(...)):
    """Upload one or more dataset files to the dataset directory."""
    results = []
    for f in files:
        if f.filename in session.processed_files:
            continue
        session.processed_files.add(f.filename)
        file_path = DATASET_DIR / f.filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = await f.read()
        file_path.write_bytes(content)
        results.append(FileInfo(name=f.filename, path=str(file_path)))
    return results


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


@router.post("/images", response_model=List[FileInfo])
async def upload_images(files: List[UploadFile] = File(...)):
    """Upload image attachments for the next message."""
    existing = {img["name"]: img["path"] for img in session.pending_images}
    saved = []

    for f in files:
        if f.filename in existing and Path(existing[f.filename]).exists():
            saved.append({"name": f.filename, "path": existing[f.filename]})
            continue

        target_path = next_available_path(UPLOADS_DIR, f.filename)
        content = await f.read()
        target_path.write_bytes(content)
        saved.append({"name": f.filename, "path": str(target_path)})

    session.pending_images = saved
    return [FileInfo(name=s["name"], path=s["path"]) for s in saved]


# ---------------------------------------------------------------------------
# PDF upload
# ---------------------------------------------------------------------------


@router.post("/pdfs", response_model=List[FileInfo])
async def upload_pdfs(files: List[UploadFile] = File(...)):
    """Upload PDF documents, optionally uploading to OpenAI Files API."""
    existing = {
        pdf["name"]: pdf
        for pdf in session.uploaded_pdfs
        if Path(pdf["path"]).exists()
    }
    saved = []

    for f in files:
        if f.filename in existing:
            saved.append(existing[f.filename])
            continue

        pdf_path = next_available_path(PDF_UPLOADS_DIR, f.filename)
        content = await f.read()
        pdf_path.write_bytes(content)

        entry = {"name": f.filename, "path": str(pdf_path)}
        try:
            file_id = upload_pdf_to_openai(pdf_path)
            entry["file_id"] = file_id
            entry["attached_to_conversation"] = False
        except Exception as e:
            logging.error(f"Failed to upload PDF {f.filename} to OpenAI: {e}")

        saved.append(entry)

    session.uploaded_pdfs = saved
    return [FileInfo(name=s["name"], path=s["path"], file_id=s.get("file_id")) for s in saved]


# ---------------------------------------------------------------------------
# File browsing
# ---------------------------------------------------------------------------


def _build_tree(directory: Path) -> List[dict]:
    """Recursively build a file tree for *directory*."""
    entries = []
    if not directory.exists():
        return entries
    for child in sorted(directory.iterdir()):
        entry = {
            "name": child.name,
            "path": str(child.relative_to(DATA_DIR)),
            "is_dir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else 0,
        }
        if child.is_dir():
            entry["children"] = _build_tree(child)
        entries.append(entry)
    return entries


@router.get("/browse")
async def browse_files():
    """Return a recursive tree listing of the data directory."""
    return _build_tree(DATA_DIR)


@router.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download a file from the data directory."""
    full_path = DATA_DIR / file_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.resolve().is_relative_to(DATA_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(full_path, filename=full_path.name)


@router.delete("/{file_path:path}")
async def delete_file(file_path: str):
    """Delete a file from the data directory."""
    full_path = DATA_DIR / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not full_path.resolve().is_relative_to(DATA_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    if full_path.is_dir():
        import shutil
        shutil.rmtree(full_path)
    else:
        full_path.unlink()
    return {"status": "deleted", "path": file_path}


@router.get("/pending-images")
async def get_pending_images():
    """Return the list of currently pending image attachments."""
    return session.pending_images


@router.get("/uploaded-pdfs")
async def get_uploaded_pdfs():
    """Return the list of currently uploaded PDFs."""
    return session.uploaded_pdfs
