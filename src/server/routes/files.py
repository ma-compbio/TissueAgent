"""REST endpoints for file management: unified upload, browsing, and download."""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import (
    ACTIVE_PROJECT_DIR,
    ACTIVE_PROJECT_ID_FILE,
    DATA_DIR,
    DATASET_DIR,
    LIBRARY_DIR,
    LIBRARY_FILES_DIR,
    PROJECT_ATTACHMENTS_DIRNAME,
    PROJECT_CHAT_FILENAME,
    PROJECT_OUTPUTS_DIRNAME,
    PROJECT_UPLOADS_DIRNAME,
)
from server.session_manager import session
from server.utils import (
    next_available_path,
    upload_pdf_to_openai,
)

router = APIRouter(prefix="/api/files")

# Extensions routed to dataset/
DATASET_EXTENSIONS = {
    ".h5ad", ".h5", ".hdf5",
    ".csv", ".tsv", ".txt",
    ".loom", ".zarr",
    ".mtx", ".mtx.gz",
    ".parquet",
    ".gz", ".tar.gz",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".svg"}


class FileInfo(BaseModel):
    """Metadata for an uploaded file."""

    name: str
    path: str
    category: str = "general"
    file_id: str | None = None


class UploadResult(BaseModel):
    """Aggregated result of a unified upload."""

    files: List[FileInfo]


class BrowseEntry(BaseModel):
    """A single entry in a directory listing."""

    name: str
    path: str
    is_dir: bool
    size: int = 0
    children: list["BrowseEntry"] | None = None


def _classify_file(filename: str) -> str:
    """Return 'dataset', 'image', 'pdf', or 'general' based on file extension."""
    lower = filename.lower()
    # Check compound extensions first (e.g. .mtx.gz, .tar.gz)
    for ext in DATASET_EXTENSIONS:
        if lower.endswith(ext):
            return "dataset"
    suffix = Path(lower).suffix
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix == ".pdf":
        return "pdf"
    return "general"


# ---------------------------------------------------------------------------
# Unified upload
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=UploadResult)
async def upload_files(
    files: List[UploadFile] = File(...),
    target: str = "project",
):
    """Upload files to the requested target.

    Args:
        files: One or more files to upload.
        target: ``project`` (default) — drop everything into the active
            project's ``uploads/`` folder. Images and PDFs are *also*
            registered on the session so they ride along on the next
            multimodal turn; the project is minted lazily if there
            isn't one yet. ``library`` — write to the persistent
            library: datasets go to ``library/datasets/``, everything
            else to ``library/files/``. Library is purely persistent
            reference data; nothing about library uploads ties them
            to the current chat.
    """
    if target not in ("project", "library"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown upload target {target!r}; expected 'project' or 'library'.",
        )

    results: List[FileInfo] = []

    # Pick the destination dirs. ``project`` target always writes into
    # the active project shell — it exists pre-mint as an empty
    # directory, so pre-mint and post-mint look identical.
    if target == "project":
        uploads_dir = ACTIVE_PROJECT_DIR / PROJECT_UPLOADS_DIRNAME
        attachments_dir = ACTIVE_PROJECT_DIR / PROJECT_ATTACHMENTS_DIRNAME
        uploads_dir.mkdir(parents=True, exist_ok=True)
        attachments_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        category = _classify_file(f.filename)
        content = await f.read()

        if target == "library":
            results.append(_save_library(f.filename, content, category))
            continue

        # target == "project". Images/PDFs go to attachments/ so the
        # multimodal turn payload finds them in a dedicated place;
        # everything else lands in uploads/.
        if category == "image":
            existing = {img["name"]: img["path"] for img in session.pending_images}
            if f.filename in existing and Path(existing[f.filename]).exists():
                results.append(FileInfo(name=f.filename, path=existing[f.filename], category="image"))
                continue
            target_path = next_available_path(attachments_dir, f.filename)
            target_path.write_bytes(content)
            session.pending_images.append({"name": f.filename, "path": str(target_path)})
            results.append(FileInfo(name=f.filename, path=str(target_path), category="image"))

        elif category == "pdf":
            existing = {
                pdf["name"]: pdf for pdf in session.uploaded_pdfs if Path(pdf["path"]).exists()
            }
            if f.filename in existing:
                entry = existing[f.filename]
                results.append(
                    FileInfo(name=f.filename, path=entry["path"], category="pdf", file_id=entry.get("file_id"))
                )
                continue
            pdf_path = next_available_path(attachments_dir, f.filename)
            pdf_path.write_bytes(content)
            entry = {"name": f.filename, "path": str(pdf_path)}
            try:
                file_id = upload_pdf_to_openai(pdf_path)
                entry["file_id"] = file_id
                entry["attached_to_conversation"] = False
            except Exception as e:
                logging.error(f"Failed to upload PDF {f.filename} to OpenAI: {e}")
            session.uploaded_pdfs.append(entry)
            results.append(FileInfo(name=f.filename, path=str(pdf_path), category="pdf", file_id=entry.get("file_id")))

        else:
            # Datasets and general files: drop them into uploads/. Don't
            # silently dedup here — if the user picks the same filename
            # twice we want both to survive, with a numeric suffix on
            # the second.
            target_path = next_available_path(uploads_dir, f.filename)
            target_path.write_bytes(content)
            if category == "dataset":
                session.processed_files.add(f.filename)
            results.append(FileInfo(name=f.filename, path=str(target_path), category=category))

    return UploadResult(files=results)


def _save_library(filename: str, content: bytes, category: str) -> FileInfo:
    """Write *content* into the appropriate library subfolder."""
    if category == "dataset":
        target_path = next_available_path(DATASET_DIR, filename)
    else:
        target_path = next_available_path(LIBRARY_FILES_DIR, filename)
    target_path.write_bytes(content)
    return FileInfo(name=filename, path=str(target_path), category=category)


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backwards compatibility)
# ---------------------------------------------------------------------------


@router.post("/dataset", response_model=List[FileInfo])
async def upload_dataset(files: List[UploadFile] = File(...)):
    """Upload one or more dataset files to the dataset directory."""
    result = await upload_files(files)
    return result.files


@router.post("/images", response_model=List[FileInfo])
async def upload_images(files: List[UploadFile] = File(...)):
    """Upload image attachments for the next message."""
    result = await upload_files(files)
    return result.files


@router.post("/pdfs", response_model=List[FileInfo])
async def upload_pdfs(files: List[UploadFile] = File(...)):
    """Upload PDF documents, optionally uploading to OpenAI Files API."""
    result = await upload_files(files)
    return result.files


# ---------------------------------------------------------------------------
# File browsing
# ---------------------------------------------------------------------------


def _build_tree(directory: Path, root: Path) -> List[dict]:
    """Recursively build a file tree for *directory*, paths relative to *root*."""
    entries = []
    if not directory.exists():
        return entries
    for child in sorted(directory.iterdir()):
        entry = {
            "name": child.name,
            "path": str(child.relative_to(root)),
            "is_dir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else 0,
        }
        if child.is_dir():
            entry["children"] = _build_tree(child, root)
        entries.append(entry)
    return entries


@router.get("/browse")
async def browse_files(scope: str = "library", project_id: str | None = None):
    """Return a file-tree listing.

    Args:
        scope: ``library`` returns the persistent library tree
            (datasets + files). ``project`` returns the active (or
            named) project, with ``attachments/`` and ``outputs/``
            stacked as two top-level directories. ``all`` returns the
            whole workspace tree (legacy / debug).
        project_id: When ``scope=project`` and the active project should
            be overridden, name it explicitly.

    The returned paths are **relative to the scope root** (which for
    ``project`` is the project folder itself, so paths look like
    ``attachments/foo.png`` or ``outputs/bar.csv``). The download and
    delete endpoints honor the same ``scope`` and resolve relative to
    that root.
    """
    if scope == "library":
        return _build_tree(LIBRARY_DIR, LIBRARY_DIR)

    if scope == "project":
        # Parked projects aren't browsable — the active project is the
        # only one the user (and the agent) can see. The ``project_id``
        # query arg is honored only when it matches the active id; any
        # other value is rejected so the API can't be coaxed into
        # listing a parked tree.
        if project_id and project_id != (session.project_id or ""):
            raise HTTPException(
                status_code=409,
                detail="Only the active project can be browsed.",
            )

        root = ACTIVE_PROJECT_DIR
        children: list[dict] = []
        for name in (
            PROJECT_UPLOADS_DIRNAME,
            PROJECT_ATTACHMENTS_DIRNAME,
            PROJECT_OUTPUTS_DIRNAME,
        ):
            sub = root / name
            if not sub.exists():
                continue
            children.append({
                "name": name,
                "path": name,
                "is_dir": True,
                "size": 0,
                "children": _build_tree(sub, root),
            })
        return children

    # Fallback: whole workspace, paths relative to DATA_DIR.
    return _build_tree(DATA_DIR, DATA_DIR)


def _resolve_scoped_path(scope: str, file_path: str, project_id: str | None) -> Path:
    """Resolve *file_path* under *scope*, guarding against traversal.

    For ``scope=project`` the root is the active project folder, so
    incoming paths look like ``attachments/foo.png`` or
    ``outputs/bar.csv``. The project's ``.chat.json`` and ``.project_id``
    are intentionally *not* reachable through this resolver — those are
    internal persistence files, not user-facing artifacts.
    """
    if scope == "library":
        root = LIBRARY_DIR
    elif scope == "project":
        if project_id and project_id != (session.project_id or ""):
            raise HTTPException(
                status_code=409,
                detail="Only the active project is accessible.",
            )
        root = ACTIVE_PROJECT_DIR
        normalized = file_path.strip().lstrip("/")
        if normalized in (PROJECT_CHAT_FILENAME, ACTIVE_PROJECT_ID_FILE):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        root = DATA_DIR  # legacy/debug

    full_path = root / file_path
    try:
        if not full_path.resolve().is_relative_to(root.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid path.")
    return full_path


@router.get("/download/{file_path:path}")
async def download_file(
    file_path: str,
    scope: str = "library",
    project_id: str | None = None,
    inline: bool = False,
):
    """Serve a file from the given scope's root.

    By default the response carries ``Content-Disposition: attachment`` so the
    browser downloads it. Pass ``inline=1`` to omit the attachment disposition,
    letting the browser render the file in place (used by the PDF previewer,
    which embeds this URL in an ``<iframe>``).
    """
    full_path = _resolve_scoped_path(scope, file_path, project_id)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if inline:
        # No filename= → Starlette omits Content-Disposition: attachment, so
        # the browser renders inline instead of forcing a download.
        return FileResponse(
            full_path,
            headers={"Content-Disposition": f'inline; filename="{full_path.name}"'},
        )
    return FileResponse(full_path, filename=full_path.name)


@router.delete("/{file_path:path}")
async def delete_file(
    file_path: str, scope: str = "library", project_id: str | None = None
):
    """Delete a file (or recursive directory) from the given scope."""
    full_path = _resolve_scoped_path(scope, file_path, project_id)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
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
