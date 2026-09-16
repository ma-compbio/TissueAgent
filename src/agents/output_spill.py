"""Spill oversized tool output to disk so truncation doesn't destroy it.

Tool results are capped at ``MAX_OUTPUT_CHARS`` before reaching the model —
necessary, since a 50k-character DataFrame dump cannot go into context. But
truncating *without* keeping the original discards it permanently: the agent's
only recourse is to re-run the cell and hope it prints less. Instead we write the
full text under the active project and put its path in the truncation notice, so
the agent can ``read`` the part it needs.

This is the text counterpart of :mod:`agents.agent_registry.coding_agent_cache.image_spill`,
which does the same for inline plot images. **The two use different path
conventions on purpose**, because they serve different consumers:

- ``image_spill`` returns paths relative to ``ACTIVE_PROJECT_DIR`` (e.g.
  ``outputs/figures/_trace/x.png``) — the form ``/api/files/download`` wants.
- This module returns paths relative to ``DATA_DIR`` (e.g.
  ``project/outputs/_trace/output/x.txt``) — the form the ``read`` tool wants,
  since ``_resolve_artifact_path`` resolves against ``DATA_DIR``.

Getting that wrong yields a path the agent cannot open, which is worse than
plain truncation: it advertises recoverable data and then 404s.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from config import ACTIVE_PROJECT_DIR, DATA_DIR, PROJECT_OUTPUTS_DIRNAME

# Under outputs/ so spilled text travels with the project on park/promote and
# survives reset_data_directories — same reasoning as image_spill's _TRACE_SUBDIR.
_TRACE_SUBDIR = f"{PROJECT_OUTPUTS_DIRNAME}/_trace/output"


def spill_text_to_disk(text: str) -> str | None:
    """Write *text* under the project's trace dir; return a DATA_DIR-relative path.

    Returns ``None`` on any failure — callers must fall back to plain truncation.
    A spill is a convenience, never a precondition: failing to write an overflow
    file must not turn a working tool call into an error.

    The returned path is the form the ``read`` tool accepts, e.g.
    ``project/outputs/_trace/output/<uuid>.txt``.
    """
    if not text:
        return None

    trace_dir = ACTIVE_PROJECT_DIR / _TRACE_SUBDIR
    dest = trace_dir / f"{uuid.uuid4().hex}.txt"
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    except Exception as e:
        logging.warning(f"Could not spill tool output to {dest}: {e}")
        return None

    try:
        return str(Path(dest).relative_to(DATA_DIR))
    except ValueError:
        # ACTIVE_PROJECT_DIR is always under DATA_DIR today; if that ever stops
        # being true, degrade rather than hand back an unreadable absolute path.
        logging.warning(f"Spilled output {dest} is outside DATA_DIR; not referencing it.")
        return None
