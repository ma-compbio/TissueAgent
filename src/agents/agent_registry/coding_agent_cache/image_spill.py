"""Spill inline plot images to disk so the UI can reference them by path.

The coding agent's ``python``/``r`` tools capture matplotlib/ggplot output as
base64 ``data:`` URIs. Persisting those inline would balloon ``.chat.json`` and
force the frontend to carry megabytes of base64 through the WebSocket. Instead
we write each image under the active project's ``outputs/figures/_trace/`` and
hand back **project-relative paths**; the frontend loads the pixels on demand
from ``/api/files/download`` (``scope=project``).
"""

from __future__ import annotations

import base64
import logging
import re
import uuid
from pathlib import Path

from config import ACTIVE_PROJECT_DIR, PROJECT_OUTPUTS_DIRNAME

# The subdirectory (under the project's outputs/) that holds spilled trace
# images. Lives under outputs/ so it travels with the project on park/promote
# and survives reset_data_directories.
_TRACE_SUBDIR = f"{PROJECT_OUTPUTS_DIRNAME}/figures/_trace"

# ``data:image/png;base64,AAAA...`` → (mime, payload)
_DATA_URI_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.DOTALL)

_EXT_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}


def spill_images_to_disk(data_uris: list[str]) -> list[str]:
    """Write base64 image data URIs to disk; return project-relative paths.

    Each returned path is relative to ``ACTIVE_PROJECT_DIR`` (e.g.
    ``outputs/figures/_trace/<uuid>.png``) — the exact form the file-download
    endpoint expects for ``scope=project``. Malformed or undecodable URIs are
    skipped (logged), never raised: a plot that fails to spill simply won't
    render in the trace, which must not break code execution.
    """
    if not data_uris:
        return []

    trace_dir = ACTIVE_PROJECT_DIR / _TRACE_SUBDIR
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.warning(f"Could not create trace image dir {trace_dir}: {e}")
        return []

    paths: list[str] = []
    for uri in data_uris:
        m = _DATA_URI_RE.match(uri or "")
        if not m:
            logging.warning("Skipping trace image: not a base64 data URI.")
            continue
        ext = _EXT_BY_MIME.get(m.group("mime").strip().lower(), "png")
        try:
            raw = base64.b64decode(m.group("data"), validate=False)
        except Exception as e:
            logging.warning(f"Skipping trace image: base64 decode failed ({e}).")
            continue
        name = f"{uuid.uuid4().hex}.{ext}"
        dest = trace_dir / name
        try:
            dest.write_bytes(raw)
        except Exception as e:
            logging.warning(f"Skipping trace image: write failed for {dest} ({e}).")
            continue
        # Path relative to ACTIVE_PROJECT_DIR — what the download endpoint wants.
        paths.append(f"{_TRACE_SUBDIR}/{name}")
    return paths
