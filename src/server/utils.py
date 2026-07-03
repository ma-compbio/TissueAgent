"""Framework-agnostic utilities extracted from the Streamlit app.

Provides file handling, message identity, session persistence, HTML export, and content-parsing helpers used by the
FastAPI server layer.
"""

import base64
import json
import logging
import mimetypes
import re
import shutil
import threading
import time
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
)

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import messages_from_dict
from langgraph.graph import MessagesState

from config import (
    ACTIVE_PROJECT_DIR,
    ACTIVE_PROJECT_ID_FILE,
    DATA_DIR,
    DATASET_DIR,
    LEGACY_SESSIONS_DIR,
    LIBRARY_DIR,
    LIBRARY_FILES_DIR,
    PLAN_SCRATCH_DIR,
    PROJECT_ATTACHMENTS_DIRNAME,
    PROJECT_CHAT_FILENAME,
    PROJECT_OUTPUTS_DIRNAME,
    PROJECT_UPLOADS_DIRNAME,
    PROJECTS_DIR,
    SESSIONS_DIR,  # alias; remove once nothing references it
)

# Guards every operation that mutates the on-disk active-project state.
# Held by switch_active_project; routes that mutate active state acquire
# it before calling helpers in this module.
_switch_lock = threading.Lock()

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def file_to_data_url(file_path: Path) -> str:
    """Convert a local file to a Base64 data URL for multimodal chat."""
    mime, _ = mimetypes.guess_type(file_path.name)
    if mime is None:
        mime = "application/octet-stream"
    b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def upload_pdf_to_openai(pdf_path: Path) -> str:
    """Upload PDF to OpenAI Files API and return file_id."""
    try:
        file = openai.files.create(file=open(pdf_path, "rb"), purpose="user_data")
        logging.info(f"Uploaded PDF {pdf_path.name} to OpenAI, file_id: {file.id}")
        return file.id
    except Exception as e:
        logging.error(f"Failed to upload PDF {pdf_path.name}: {e}")
        raise


def next_available_path(directory: Path, filename: str) -> Path:
    """Return a unique path inside *directory* by suffixing an index if needed."""
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for idx in range(1, 1000):
        candidate = directory / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Unable to allocate a unique filename for {filename}")


def reset_data_directories() -> None:
    """Ensure the workspace tree exists; wipe only the ephemeral parts.

    Preserved across restarts:
        - ``LIBRARY_DIR`` (persistent shared input)
        - ``ACTIVE_PROJECT_DIR`` (the currently-active project's home;
          actual contents are restored by ``recover_active_project``)
        - ``PROJECTS_DIR`` (parked projects, outside DATA_DIR)
        - ``LEGACY_SESSIONS_DIR`` (so the one-shot migration at startup
          can still find old session files; gone after migration)

    Reset every boot:
        - ``PLAN_SCRATCH_DIR`` (the in-flight plan store)
        - Anything else under ``DATA_DIR`` that isn't on the preserve list
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_FILES_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    preserve = {LIBRARY_DIR, ACTIVE_PROJECT_DIR}
    for child in DATA_DIR.iterdir():
        if not child.is_dir() or child in preserve:
            continue
        shutil.rmtree(child, ignore_errors=True)

    # Plan scratch lives outside DATA_DIR (see config.py); ensure it exists.
    PLAN_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)


def migrate_legacy_library_layout() -> None:
    """Reshape any older library/ folder into the current layout.

    Older layouts had::

        library/
        ├── dataset/      (singular)
        ├── uploads/      (chat-attached images, accidentally persistent)
        └── pdfs/         (chat-attached PDFs, ditto)

    The current layout is::

        library/
        ├── datasets/     (plural — curated reference data)
        └── files/        (persistent reference uploads)

    This routine:
        1. Renames ``library/dataset/`` → ``library/datasets/``.
        2. Moves any files from ``library/uploads/`` and
           ``library/pdfs/`` into ``library/files/`` (best-effort; on
           name clash the source filename is suffixed).
        3. Removes the now-empty legacy subdirs.

    Idempotent. Safe to run on a fresh install (no-op).
    """
    if not LIBRARY_DIR.exists():
        return

    # 1) Rename dataset → datasets
    legacy_dataset = LIBRARY_DIR / "dataset"
    if legacy_dataset.exists() and not DATASET_DIR.exists():
        try:
            legacy_dataset.rename(DATASET_DIR)
            logging.info("Renamed library/dataset → library/datasets")
        except Exception as e:
            logging.warning(f"Failed to rename library/dataset: {e}")
    elif legacy_dataset.exists():
        # Both exist (unlikely): merge legacy into new.
        for src in legacy_dataset.iterdir():
            dst = next_available_path(DATASET_DIR, src.name)
            try:
                shutil.move(str(src), str(dst))
            except Exception as e:
                logging.warning(f"Failed to migrate {src}: {e}")
        shutil.rmtree(legacy_dataset, ignore_errors=True)

    # 2) Consolidate uploads/ + pdfs/ into files/
    LIBRARY_FILES_DIR.mkdir(parents=True, exist_ok=True)
    for legacy_name in ("uploads", "pdfs"):
        legacy = LIBRARY_DIR / legacy_name
        if not legacy.exists() or legacy == LIBRARY_FILES_DIR:
            continue
        for src in legacy.iterdir():
            if src.is_file():
                dst = next_available_path(LIBRARY_FILES_DIR, src.name)
                try:
                    shutil.move(str(src), str(dst))
                except Exception as e:
                    logging.warning(f"Failed to migrate {src}: {e}")
        shutil.rmtree(legacy, ignore_errors=True)


def migrate_legacy_sessions() -> None:
    """One-shot move of ``sessions/session_*.json`` → ``projects/<id>/.chat.json``.

    Idempotent. Runs once at startup. After the move, the legacy
    ``sessions/`` directory is left in place (now empty) so an aborted
    migration can be retried; a follow-up boot will see an empty source
    and no-op.
    """
    if not LEGACY_SESSIONS_DIR.exists():
        return

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for src in LEGACY_SESSIONS_DIR.glob(
        f"{SESSION_FILENAME_PREFIX}*{SESSION_FILENAME_SUFFIX}"
    ):
        stem = src.stem
        if stem.startswith(SESSION_FILENAME_PREFIX):
            stem = stem[len(SESSION_FILENAME_PREFIX):]
        if not stem:
            continue

        project_dir = PROJECTS_DIR / stem
        chat_file = project_dir / PROJECT_CHAT_FILENAME
        if chat_file.exists():
            continue  # Already migrated.

        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / PROJECT_OUTPUTS_DIRNAME).mkdir(exist_ok=True)
        try:
            shutil.move(str(src), str(chat_file))
            moved += 1
        except Exception as e:
            logging.warning(f"Failed to migrate {src}: {e}")

    # ``sessions/active/`` previously held the in-flight plan — drop it
    # if it's still around; plan_store now lives at PLAN_SCRATCH_DIR.
    legacy_active = LEGACY_SESSIONS_DIR / "active"
    if legacy_active.exists():
        shutil.rmtree(legacy_active, ignore_errors=True)

    if moved:
        logging.info(f"Migrated {moved} legacy session(s) to projects/.")


def migrate_projects_out_of_workspace() -> None:
    """Move any ``workspace/projects/<id>/`` → ``<ROOT>/projects/<id>/``.

    Used to live inside DATA_DIR (agent-visible); now lives outside it
    so parked projects are unreachable through tool calls. Idempotent.
    """
    old_root = DATA_DIR / "projects"
    if not old_root.exists() or old_root.resolve() == PROJECTS_DIR.resolve():
        return

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for child in list(old_root.iterdir()):
        if not child.is_dir():
            continue
        dest = PROJECTS_DIR / child.name
        if dest.exists():
            logging.warning(
                f"Skipping migration of {child} — destination {dest} already exists."
            )
            continue
        try:
            shutil.move(str(child), str(dest))
            moved += 1
        except Exception as e:
            logging.warning(f"Failed to migrate {child}: {e}")

    # Drop the now-empty old directory so it doesn't shadow the agent's
    # view of the workspace.
    try:
        if not any(old_root.iterdir()):
            old_root.rmdir()
    except Exception:
        pass

    if moved:
        logging.info(f"Moved {moved} parked project(s) out of workspace.")


def migrate_plan_scratch_out_of_workspace() -> None:
    """Move ``workspace/plan_scratch/`` → ``<ROOT>/plan_scratch/``. Idempotent."""
    old = DATA_DIR / "plan_scratch"
    if not old.exists() or old.resolve() == PLAN_SCRATCH_DIR.resolve():
        return

    PLAN_SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    for child in list(old.iterdir()):
        dest = PLAN_SCRATCH_DIR / child.name
        if dest.exists():
            continue
        try:
            shutil.move(str(child), str(dest))
        except Exception as e:
            logging.warning(f"Failed to migrate plan scratch {child}: {e}")
    try:
        if not any(old.iterdir()):
            old.rmdir()
    except Exception:
        pass


def migrate_chat_json_to_dotfile() -> None:
    """Rename ``chat.json`` → ``.chat.json`` in active and parked projects.

    The dotfile naming hides the persistence file from default ``glob('**/*')``
    patterns in agent tools. Idempotent.
    """
    candidates: List[Path] = []
    if PROJECTS_DIR.exists():
        for child in PROJECTS_DIR.iterdir():
            if child.is_dir():
                candidates.append(child / "chat.json")
    candidates.append(ACTIVE_PROJECT_DIR / "chat.json")

    renamed = 0
    for old in candidates:
        if not old.exists():
            continue
        new = old.with_name(PROJECT_CHAT_FILENAME)
        if new.exists():
            continue
        try:
            old.rename(new)
            renamed += 1
        except Exception as e:
            logging.warning(f"Failed to rename {old} → {new}: {e}")
    if renamed:
        logging.info(f"Renamed {renamed} chat.json → {PROJECT_CHAT_FILENAME}.")


def migrate_scratch_into_active_project() -> None:
    """Drain legacy ``workspace/scratch/{uploads,attachments}/*`` into
    ``workspace/project/{uploads,attachments}/``.

    No-op if the old scratch dir doesn't exist. Idempotent.
    """
    old_root = DATA_DIR / "scratch"
    if not old_root.exists():
        return

    ACTIVE_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for sub, dest_name in (("uploads", PROJECT_UPLOADS_DIRNAME),
                            ("attachments", PROJECT_ATTACHMENTS_DIRNAME)):
        src_dir = old_root / sub
        if not src_dir.exists():
            continue
        dst_dir = ACTIVE_PROJECT_DIR / dest_name
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in list(src_dir.iterdir()):
            if not src.is_file():
                continue
            dst = next_available_path(dst_dir, src.name)
            try:
                shutil.move(str(src), str(dst))
                moved += 1
            except Exception as e:
                logging.warning(f"Failed to migrate scratch file {src}: {e}")

    try:
        shutil.rmtree(old_root, ignore_errors=True)
    except Exception:
        pass

    if moved:
        logging.info(f"Migrated {moved} scratch file(s) into active project.")


# ---------------------------------------------------------------------------
# Message identity & filtering
# ---------------------------------------------------------------------------


def message_identity(message: Any) -> str:
    """Return a stable string key for *message* used to de-duplicate display."""
    msg_id = getattr(message, "id", None)
    if msg_id:
        return str(msg_id)
    try:
        data = message.model_dump()
    except AttributeError:
        data = {
            "type": getattr(message, "type", type(message).__name__),
            "name": getattr(message, "name", None),
            "content": getattr(message, "content", None),
            "tool_calls": getattr(message, "tool_calls", None),
        }
    return json.dumps(data, sort_keys=True, default=str)


def should_hide_message(message: Any) -> bool:
    """Return True for messages that should not appear in the display stream."""
    if isinstance(message, HumanMessage):
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.startswith("Python Output:\n"):
            return True
    return False


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def flatten_text_chunks(chunks: Sequence[Any]) -> str:
    """Return human-readable text extracted from LangChain content chunks."""
    texts: List[str] = []
    for part in chunks:
        if isinstance(part, dict):
            if part.get("type") in {"text", "output_text"}:
                texts.append(part.get("text", ""))
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(t for t in texts if t).strip()


def stringify_chat_content(content: Any) -> str:
    """Convert message content into a plain-text representation."""
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        return flatten_text_chunks(content)
    if content is None:
        return ""
    return str(content)


def extract_tool_inputs(
    tool_calls: Optional[Iterable[Mapping[str, Any]]],
    sink: MutableMapping[str, str],
) -> List[str]:
    """Collect tool inputs keyed by call id and return a list of tool names."""
    names: List[str] = []
    if not tool_calls:
        return names
    for call in tool_calls:
        name = str(call.get("name", ""))
        tool_id = str(call.get("id", "")) or None
        raw_args = call.get("args", {})
        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed_args = raw_args
        else:
            parsed_args = raw_args
        if tool_id:
            sink[tool_id] = json.dumps(parsed_args, indent=2, ensure_ascii=False)
        names.append(name)
    return names


def split_route_and_body(content: str) -> Tuple[Optional[str], str]:
    """Separate the optional ROUTE header from the remaining message body."""
    lines = [line for line in content.strip().splitlines() if line.strip()]
    if lines and lines[0].upper().startswith("ROUTE:"):
        route_caption = lines[0].split(":", 1)[-1].strip()
        body = "\n".join(lines[1:]).strip()
        return route_caption or None, body
    return None, content.strip()


def extract_html_tags(content: str) -> Optional[Dict[str, str]]:
    """Extract <execute>, <response>, <scratchpad>, or <plan> tags (case insensitive)."""
    allowed_tags = ["execute", "response", "scratchpad", "plan"]
    pattern = r"<(" + "|".join(re.escape(tag) for tag in allowed_tags) + r")>(.*?)(?:</\1>|$)"
    pattern = re.compile(pattern, re.IGNORECASE | re.DOTALL)
    matches = pattern.findall(content)
    if not matches:
        return None
    result = {}
    for tag, content_text in matches:
        result[tag.lower()] = content_text.strip()
    return result


# ---------------------------------------------------------------------------
# Agent identity metadata
# ---------------------------------------------------------------------------

AvatarLabel = Tuple[str, str]

MAIN_AGENT_BADGES: Dict[str, AvatarLabel] = {
    "planner_agent": ("🧠", "Planner"),
    "recruiter_agent": ("🧑\u200d🤝\u200d🧑", "Recruiter"),
    "manager_agent": ("🧭", "Manager"),
    "evaluator_agent": ("🧪", "Evaluator"),
    "reporter_agent": ("📝", "Reporter"),
}

SUBAGENT_BADGES: Dict[str, str] = {
    "Coding Agent": "💻",
    "Searcher Agent": "🔍",
    "Single Cell Agent": "🧫",
    "Gene Agent": "🧬",
}

DEFAULT_AGENT_AVATAR = "🤖"
DEFAULT_AGENT_LABEL = "Assistant"
SUBAGENT_DEFAULT_AVATAR = "🧩"
USER_AVATAR = "🧑\u200d🔬"


def lookup_agent_badge(agent_name: Optional[str]) -> AvatarLabel:
    """Return the avatar and label for the given agent name."""
    if not agent_name:
        return DEFAULT_AGENT_AVATAR, DEFAULT_AGENT_LABEL
    if agent_name in MAIN_AGENT_BADGES:
        return MAIN_AGENT_BADGES[agent_name]
    friendly = agent_name.replace("_agent", "").replace("_", " ").title()
    return DEFAULT_AGENT_AVATAR, friendly or DEFAULT_AGENT_LABEL


# ---------------------------------------------------------------------------
# Image stripping
# ---------------------------------------------------------------------------


def strip_images_for_display(messages):
    """Return deep-copied messages with image content blocks removed."""
    cleaned = []
    for m in messages:
        if hasattr(m, "model_copy"):
            m2 = m.model_copy(deep=True)
        else:
            m2 = deepcopy(m)
        if hasattr(m, "name"):
            setattr(m2, "name", getattr(m, "name", None))
        c = getattr(m2, "content", None)
        if isinstance(c, list):
            texts = []
            for part in c:
                if isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                    texts.append(part.get("text", ""))
            m2.content = "\n".join(texts).strip()
        cleaned.append(m2)
    return cleaned


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

SESSION_FILENAME_PREFIX = "session_"
SESSION_FILENAME_SUFFIX = ".json"


def message_to_serializable(message):
    """Convert a message to a serializable format for saving."""
    data = message.model_dump()
    data.pop("type", None)
    return {"type": message.type, "data": data}


_TITLE_MAX_LEN = 60


def collect_prompts_snapshot() -> Dict[str, str]:
    """Capture the system prompts of every registered agent.

    Walks both the five main pipeline agents and every specialist in
    :data:`agents.agent_defns.AgentDefns`. Prompts that are produced by
    a callable (rather than a literal string) are rendered with the same
    ``agent_id_descriptions`` mapping the runtime uses, so the snapshot
    matches what the model actually saw.

    Returns a flat ``{agent_id: prompt_text}`` mapping. Missing or
    unresolvable prompts are silently skipped — the snapshot is best
    effort and must never fail the save call.
    """
    snapshot: Dict[str, str] = {}

    try:
        from agents.agent_defns import (
            AgentDefns,
            PlannerAgent,
            RecruiterAgent,
            ManagerAgent,
            EvaluatorAgent,
            ReporterAgent,
        )
    except Exception:
        return snapshot

    # The recruiter/manager prompts are callables that take a mapping of
    # {node_id: description}. Build that mapping the same way graph.py
    # does so the snapshot matches the runtime prompt.
    try:
        agent_id_descriptions = {
            f"{a.id}_agent": getattr(a, "description", "") for a in AgentDefns
        }
    except Exception:
        agent_id_descriptions = {}

    main_agents = [
        PlannerAgent,
        RecruiterAgent,
        ManagerAgent,
        EvaluatorAgent,
        ReporterAgent,
    ]
    for agent in main_agents:
        try:
            prompt = getattr(agent, "prompt", None)
            if callable(prompt):
                rendered = prompt(agent_id_descriptions)
            else:
                rendered = prompt
            if isinstance(rendered, str) and rendered.strip():
                snapshot[agent.id] = rendered
        except Exception:
            continue

    for agent in AgentDefns:
        try:
            prompt = getattr(agent, "prompt", None)
            if prompt is None:
                # CustomAgents (coding, hypothesis) don't expose a single
                # string prompt — their prompts are constructed inside the
                # ctor closure. Skip; ``description`` already records what
                # the registry knows about them.
                continue
            if callable(prompt):
                rendered = prompt(agent_id_descriptions)
            else:
                rendered = prompt
            if isinstance(rendered, str) and rendered.strip():
                snapshot[agent.id] = rendered
        except Exception:
            continue

    return snapshot


def derive_session_title(messages: Sequence[BaseMessage]) -> str:
    """Pick a short title for a saved session from its first user message.

    Returns an empty string when no usable text is found. The caller decides how to fall back (typically to the
    timestamp).
    """
    for m in messages:
        if isinstance(m, HumanMessage):
            text = stringify_chat_content(m.content).strip()
            if not text:
                continue
            # Single line, ellipsised at TITLE_MAX_LEN chars.
            first_line = text.splitlines()[0].strip()
            if len(first_line) > _TITLE_MAX_LEN:
                first_line = first_line[: _TITLE_MAX_LEN - 1].rstrip() + "…"
            return first_line
    return ""


def format_session_label(session_path: Path) -> str:
    """Format a session path into a human-readable timestamp label."""
    stem = session_path.stem
    if stem.startswith(SESSION_FILENAME_PREFIX):
        stem = stem[len(SESSION_FILENAME_PREFIX):]
    try:
        saved_at = datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
        return saved_at.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def session_option_label(session_path: Path, title: str = "") -> str:
    """Create a label for the session selection dropdown.

    Combines the title (when available) with the timestamp. Falls back to the raw timestamp when no title was saved.
    """
    ts = format_session_label(session_path)
    return f"{title} — {ts}" if title else ts


def save_session(
    messages: List[BaseMessage],
    subagent_states: Dict,
    uploaded_pdfs: List[Dict],
    replan_count: int,
    replan_history: List,
    recruiter_retry_count: int = 0,
    mode: str = "autopilot",
    plan_markdown: str = "",
    prompts_snapshot: Optional[Dict[str, str]] = None,
    project_id: Optional[str] = None,
) -> Path:
    """Save a chat session to a timestamped JSON file.

    Args:
        messages: The conversation message list.
        subagent_states: Mapping of tool IDs to (agent_name, state) tuples.
        uploaded_pdfs: List of uploaded PDF metadata dicts.
        replan_count: Current replan count.
        replan_history: List of replan timestamps.
        recruiter_retry_count: Current recruiter validation retry count.
        mode: Execution mode at save time ("autopilot" or "copilot").
        plan_markdown: The current evolving plan as on-disk markdown.
            Saved verbatim so it can be restored on load and rendered in
            HTML exports.
        prompts_snapshot: Optional mapping of agent name to system prompt text,
            captured at save time for inclusion in session exports.

    Returns:
        Path to the saved session file.

    Raises:
        ValueError: If there are no messages to save.
    """
    if not messages:
        raise ValueError("No conversation history to save.")

    # ``project_id`` is the stable on-disk identifier — also the folder
    # name under ``projects/``. When omitted (manual-save path), mint a
    # fresh timestamp-based id so the save is unique.
    saved_at = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    stem = project_id or saved_at

    payload = {
        "saved_at": saved_at,
        "title": derive_session_title(messages),
        "messages": [message_to_serializable(m) for m in messages],
        "subagent_states": subagent_states,
        "uploaded_pdfs": uploaded_pdfs,
        "replan_count": replan_count,
        "replan_history": replan_history,
        "recruiter_retry_count": recruiter_retry_count,
        "mode": mode,
        "plan_markdown": plan_markdown,
        "prompts_snapshot": prompts_snapshot or {},
    }

    project_dir = project_dir_for(stem)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / PROJECT_OUTPUTS_DIRNAME).mkdir(exist_ok=True)
    target_path = project_dir / PROJECT_CHAT_FILENAME
    target_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return target_path


# ---------------------------------------------------------------------------
# Active project resolution
#
# The active project lives at ACTIVE_PROJECT_DIR. Parked projects live at
# PROJECTS_DIR/<id>/. The functions below route per-project paths to the
# active home when the id matches, and to the parked location otherwise.
# ---------------------------------------------------------------------------


def read_active_project_id() -> Optional[str]:
    """Return the active project's id, or None if no project is bound."""
    pid_file = ACTIVE_PROJECT_DIR / ACTIVE_PROJECT_ID_FILE
    if not pid_file.exists():
        return None
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return raw or None


def write_active_project_id(pid: str) -> None:
    """Record the active project's id in ``project/.project_id``."""
    ACTIVE_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    (ACTIVE_PROJECT_DIR / ACTIVE_PROJECT_ID_FILE).write_text(pid, encoding="utf-8")


def project_dir_for(project_id: str) -> Path:
    """Return the on-disk folder for ``project_id``.

    Returns ``ACTIVE_PROJECT_DIR`` when the id matches the active project,
    otherwise the parked path under PROJECTS_DIR.
    """
    if project_id and project_id == read_active_project_id():
        return ACTIVE_PROJECT_DIR
    return PROJECTS_DIR / project_id


def project_outputs_dir(project_id: str) -> Path:
    """Return the per-project outputs directory; creates it if missing."""
    out = project_dir_for(project_id) / PROJECT_OUTPUTS_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def project_attachments_dir(project_id: str) -> Path:
    """Return the per-project attachments directory; creates it if missing."""
    out = project_dir_for(project_id) / PROJECT_ATTACHMENTS_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def project_uploads_dir(project_id: str) -> Path:
    """Return the per-project sidebar uploads directory; creates it if missing."""
    out = project_dir_for(project_id) / PROJECT_UPLOADS_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    return out


def clear_active_project_dir() -> None:
    """Wipe the active project dir back to a clean empty shell.

    Removes ``.project_id``, deletes all children, recreates the canonical
    three subdirs. The directory itself is preserved (it must always exist).
    """
    ACTIVE_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    for child in list(ACTIVE_PROJECT_DIR.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink()
        except Exception as e:
            logging.warning(f"Failed to clear active-project entry {child}: {e}")
    for sub in (
        PROJECT_UPLOADS_DIRNAME,
        PROJECT_ATTACHMENTS_DIRNAME,
        PROJECT_OUTPUTS_DIRNAME,
    ):
        (ACTIVE_PROJECT_DIR / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Project switch protocol
# ---------------------------------------------------------------------------


class SwitchCollisionError(RuntimeError):
    """The destination for a park already exists — refuse to silently merge."""


class SwitchMissingError(RuntimeError):
    """The requested new project doesn't exist under PROJECTS_DIR."""


def _force_kernel_restart() -> None:
    """Best-effort kernel teardown around a project switch. Lazily imported."""
    try:
        from config import active_project_outputs
        from server.main import set_kernel_workspace
        set_kernel_workspace(active_project_outputs(), force_restart=True)
    except Exception as e:
        logging.warning(f"Kernel teardown failed during switch: {e}")


def _rearm_kernel() -> None:
    """Post-switch: re-arm the kernel for the (possibly new) contents."""
    try:
        from config import active_project_outputs
        from server.main import set_kernel_workspace
        set_kernel_workspace(active_project_outputs(), force_restart=False)
    except Exception as e:
        logging.warning(f"Kernel re-arm failed after switch: {e}")


def switch_active_project(new_id: Optional[str]) -> None:
    """Atomically swap the active project to ``new_id`` (or to "empty shell").

    Protocol:
        1. Force-kill kernels (path string is invariant; equality check
           in ``set_workspace`` won't fire on its own).
        2. If a project is currently active, park it
           (``project/`` → ``projects/<old_id>/``).
        3. If ``new_id`` is given, promote
           (``projects/<new_id>/`` → ``project/``); else recreate an
           empty shell.
        4. Re-arm the kernel.

    Concurrency: holds ``_switch_lock`` for the entire body. Callers
    must already have checked ``session.is_running`` if they want to
    refuse mid-turn switches (routes do this today).
    """
    with _switch_lock:
        old_id = read_active_project_id()
        if new_id == old_id:
            return

        _force_kernel_restart()

        # 2. Park current project/ → projects/<old_id>/.
        if old_id is not None:
            dest = PROJECTS_DIR / old_id
            if dest.exists():
                raise SwitchCollisionError(old_id)
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            ACTIVE_PROJECT_DIR.rename(dest)

        # 3. Promote projects/<new_id>/ → project/, or recreate empty shell.
        try:
            if new_id is not None:
                src = PROJECTS_DIR / new_id
                if not src.exists():
                    raise SwitchMissingError(new_id)
                # If we're here with ACTIVE_PROJECT_DIR still present, it
                # means step 2 didn't park (old_id was None) — i.e. we're
                # promoting over an anonymous shell. Remove it so the
                # rename has a clean target.
                if ACTIVE_PROJECT_DIR.exists():
                    shutil.rmtree(ACTIVE_PROJECT_DIR)
                src.rename(ACTIVE_PROJECT_DIR)
                for sub in (
                    PROJECT_UPLOADS_DIRNAME,
                    PROJECT_ATTACHMENTS_DIRNAME,
                    PROJECT_OUTPUTS_DIRNAME,
                ):
                    (ACTIVE_PROJECT_DIR / sub).mkdir(exist_ok=True)
                write_active_project_id(new_id)
            else:
                ACTIVE_PROJECT_DIR.mkdir(exist_ok=True)
                clear_active_project_dir()
        except SwitchMissingError:
            # Roll back step 2 so we leave a consistent state.
            if old_id is not None:
                try:
                    (PROJECTS_DIR / old_id).rename(ACTIVE_PROJECT_DIR)
                except Exception as e:
                    logging.error(
                        f"Failed to roll back park of {old_id} after missing "
                        f"new project {new_id}: {e}"
                    )
            raise

        # Update in-memory session state to match.
        try:
            from server.session_manager import session
            session.project_id = new_id
            if new_id is None:
                session.project_title = ""
        except Exception:
            pass

        _rearm_kernel()


def recover_active_project() -> Optional[str]:
    """Reconcile on-disk state at startup. Returns active id or None.

    State table:
        B.1 project/ absent           → mkdir empty shell, return None
        B.2 project/ + .project_id    → return that id
        B.3 project/ no .project_id   → return None (anonymous shell)
        B.4 project/ AND parked twin  → rename twin to __rescued_<ts>,
                                         keep live, return id
        B.5 only parked exists        → mkdir empty shell, return None
    """
    ACTIVE_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in (
        PROJECT_UPLOADS_DIRNAME,
        PROJECT_ATTACHMENTS_DIRNAME,
        PROJECT_OUTPUTS_DIRNAME,
    ):
        (ACTIVE_PROJECT_DIR / sub).mkdir(exist_ok=True)

    pid = read_active_project_id()
    if pid is None:
        return None
    # Validate per the same rules as the route normalizer.
    if not pid or "/" in pid or "\\" in pid or pid in (".", ".."):
        logging.warning(f"Invalid .project_id contents: {pid!r}; ignoring.")
        return None

    parked = PROJECTS_DIR / pid
    if parked.exists():
        # B.4 — collision. The live folder is what's in front of the user;
        # rename the parked twin out of the way for forensics.
        rescue = PROJECTS_DIR / f"{pid}__rescued_{int(time.time())}"
        try:
            parked.rename(rescue)
            logging.warning(
                f"Rescued conflicting parked project {pid} → {rescue.name}"
            )
        except Exception as e:
            logging.error(f"Failed to rescue conflicting parked {pid}: {e}")
    return pid


def list_project_chat_files() -> List[Path]:
    """Return all chat files (active + parked), newest mtime first.

    Includes ``ACTIVE_PROJECT_DIR / .chat.json`` (if a ``.project_id`` is
    present) plus every ``PROJECTS_DIR / <id> / .chat.json``. Deduped by
    id so the active project isn't double-counted.
    """
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    seen_ids: set = set()
    chats: List[Path] = []

    active_pid = read_active_project_id()
    if active_pid is not None:
        active_chat = ACTIVE_PROJECT_DIR / PROJECT_CHAT_FILENAME
        if active_chat.exists():
            chats.append(active_chat)
            seen_ids.add(active_pid)

    for child in PROJECTS_DIR.iterdir():
        if not child.is_dir() or child.name in seen_ids:
            continue
        chat = child / PROJECT_CHAT_FILENAME
        if chat.exists():
            chats.append(chat)

    chats.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return chats


def load_session(path: Path) -> Dict[str, Any]:
    """Load a chat session from a JSON file.

    Args:
        path: Path to the session JSON file.

    Returns:
        Dict with keys: messages, subagent_states, uploaded_pdfs,
        replan_count, replan_history.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    restored_messages = messages_from_dict(payload.get("messages", []))
    mode = payload.get("mode", "autopilot")
    if mode not in ("autopilot", "copilot"):
        mode = "autopilot"
    snapshot_raw = payload.get("prompts_snapshot") or {}
    if not isinstance(snapshot_raw, dict):
        snapshot_raw = {}
    return {
        "messages": restored_messages,
        "subagent_states": payload.get("subagent_states", {}),
        "uploaded_pdfs": payload.get("uploaded_pdfs", []),
        "replan_count": payload.get("replan_count", 0),
        "replan_history": payload.get("replan_history", []),
        "recruiter_retry_count": payload.get("recruiter_retry_count", 0),
        "mode": mode,
        "plan_markdown": payload.get("plan_markdown", "") or "",
        "title": payload.get("title", "") or "",
        "prompts_snapshot": {k: str(v) for k, v in snapshot_raw.items()},
    }


def read_session_title(path: Path) -> str:
    """Cheap title lookup without parsing the whole message list.

    Used by the list endpoint so we don't deserialise every saved session's messages just to render the dropdown.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload.get("title", "") or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------


def _safe_pretty_json(obj: Any) -> str:
    """Safely format an object as pretty JSON."""
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _html_preserve_newlines(text: str) -> str:
    """Escape *text* for HTML and convert newlines to <br/> tags."""
    if not text:
        return ""
    return "<br/>".join(escape(text).splitlines())


def _format_message_content_for_html(content) -> str:
    """Format message content for HTML export."""
    if isinstance(content, str):
        return f"<p>{escape(content)}</p>"
    if isinstance(content, list):
        html_parts = []
        for part in content:
            if not isinstance(part, dict):
                html_parts.append(f"<p>{escape(str(part))}</p>")
                continue
            part_type = part.get("type")
            if part_type in {"text", "output_text"}:
                html_parts.append(f"<p>{escape(part.get('text', ''))}</p>")
            elif part_type == "image_url":
                image_url = part.get("image_url", {}).get("url")
                if image_url:
                    html_parts.append(
                        '<div><em>Image Attachment:</em><br/>'
                        '<img src="{}" alt="image attachment"'
                        ' style="max-width: 100%; height: auto;"/>'
                        "</div>".format(escape(image_url))
                    )
            else:
                html_parts.append(f"<pre>{escape(_safe_pretty_json(part))}</pre>")
        return "\n".join(html_parts)
    return f"<pre>{escape(repr(content))}</pre>"


def _subagent_state_to_html(agent_name: str, final_state: Any) -> str:
    """Render a sub-agent's final state as an HTML block."""
    header = f'<div class="subagent-block"><h4>{escape(agent_name or "Subagent")}</h4>'
    if not isinstance(final_state, Mapping):
        return header + f"<p>{escape(str(final_state))}</p></div>"
    messages = final_state.get("messages")
    if not messages:
        return header + "<p>No transcript available.</p></div>"
    rows = []
    for msg in messages:
        role = getattr(msg, "type", "message").title()
        body = _html_preserve_newlines(stringify_chat_content(getattr(msg, "content", "")))
        rows.append(f"<p><strong>{escape(role)}</strong>: {body}</p>")
    return header + "".join(rows) + "</div>"


def _render_conversation_history_html(
    messages: Sequence[BaseMessage],
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
) -> str:
    """Convert a full message history into styled HTML blocks."""
    blocks: List[str] = []
    for idx, message in enumerate(messages, start=1):
        if isinstance(message, HumanMessage):
            content = _html_preserve_newlines(stringify_chat_content(message.content))
            body = f"<p>{content}</p>"
            blocks.append(f'<div class="message role-user"><h3>{idx}. User</h3>{body}</div>')
            continue
        if isinstance(message, AIMessage):
            content_raw = stringify_chat_content(message.content)
            if not content_raw:
                continue
            avatar, role_label = lookup_agent_badge(message.name)
            route_caption, body_text = split_route_and_body(content_raw)
            body_parts = []
            html_tags = extract_html_tags(body_text)
            if html_tags:
                for tag, text in html_tags.items():
                    body_parts.append(f'<span class="tag-label">{escape(tag)}</span>')
                    body_parts.append(f"<p>{_html_preserve_newlines(text)}</p>")
            else:
                body_parts.append(f"<p>{_html_preserve_newlines(body_text)}</p>")
            if route_caption:
                body_parts.append(f'<div class="route-pill">{escape(route_caption)}</div>')
            header = f"<h3>{idx}. {escape(role_label)}</h3>"
            blocks.append(f'<div class="message role-ai">{header}{"".join(body_parts)}</div>')
            continue
        if isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", "") or "Tool"
            header = f"<h3>{idx}. Tool — {escape(tool_name)}</h3>"
            body_parts = [
                f"<p>{_html_preserve_newlines(stringify_chat_content(message.content))}</p>"
            ]
            tool_id = getattr(message, "id", None)
            if tool_id is not None and str(tool_id) in subagent_state:
                entry = subagent_state[str(tool_id)]
                agent_name, final_state = entry[0], entry[1]
                body_parts.append(_subagent_state_to_html(agent_name, final_state))
            blocks.append(f'<div class="message role-tool">{header}{"".join(body_parts)}</div>')
    return "\n".join(blocks)


def _render_plan_html(plan_markdown: str, plan_doc=None) -> str:
    """Render a saved plan markdown blob as a top-of-document HTML block.

    If *plan_doc* is provided it takes precedence over re-parsing *plan_markdown*. Callers should pass *plan_doc* when
    they have already enriched it with run-time data (e.g. ``params`` populated by ``annotate_steps_with_params``) that
    isn't carried in the on-disk markdown.

    Returns an empty string when there is no plan — callers should elide the section entirely in that case rather than
    print an empty box.
    """
    if plan_doc is None:
        if not plan_markdown or not plan_markdown.strip():
            return ""
        # Parse via plan_store so the HTML matches what the UI shows.
        # Imported lazily so this module stays import-cheap.
        from server.plan_store import _parse_markdown

        doc = _parse_markdown(plan_markdown)
    else:
        doc = plan_doc
    if not doc.steps:
        return ""

    rows: List[str] = []
    rows.append('<section class="plan-export">')
    rows.append("<h2>Plan</h2>")
    rows.append(
        f'<div class="plan-meta">'
        f'<span class="plan-status-pill plan-status-{escape(doc.status)}">'
        f"{escape(doc.status)}</span>"
        + (
            ' <span class="plan-edited">edited by you</span>'
            if doc.last_edited_by == "user"
            else ""
        )
        + "</div>"
    )
    if doc.provenance.template_names:
        names = ", ".join(f"<code>{escape(n)}</code>" for n in doc.provenance.template_names)
        prov_text = f"From template{'s' if len(doc.provenance.template_names) > 1 else ''}: {names}"
    else:
        prov_text = "De novo plan (no template used)"
    if doc.provenance.justification:
        prov_text += f" &mdash; {escape(doc.provenance.justification)}"
    rows.append(f'<div class="plan-provenance-line">{prov_text}</div>')
    if doc.user_request:
        rows.append(
            f'<div class="plan-request"><strong>Request:</strong> '
            f"{escape(doc.user_request)}</div>"
        )

    rows.append('<ol class="plan-steps">')
    for step in doc.steps:
        rows.append('<li class="plan-step">')
        rows.append(
            f'<div class="plan-step-head">'
            f'<span class="plan-step-num">Step {step.id}</span> '
            f'<span class="plan-step-title">{escape(step.title)}</span> '
            f'<span class="plan-step-badge plan-status-{escape(step.status)}">'
            f"{escape(step.status)}</span>"
            "</div>"
        )
        if step.description:
            rows.append(
                f'<p><strong>Description:</strong> {escape(step.description)}</p>'
            )
        if step.reasoning:
            rows.append(
                f'<p><strong>Reasoning:</strong> {escape(step.reasoning)}</p>'
            )
        if step.assigned_agent:
            rationale = (
                f' — {escape(step.assignment_rationale)}'
                if step.assignment_rationale
                else ""
            )
            rows.append(
                f'<p><strong>Assigned:</strong> '
                f'<code>{escape(step.assigned_agent)}</code>{rationale}</p>'
            )
        if step.expected_artifacts:
            items = "".join(
                f"<li><code>{escape(a)}</code></li>" for a in step.expected_artifacts
            )
            rows.append(
                f'<div class="plan-step-artifacts">'
                f'<strong>Expected artifacts:</strong><ul>{items}</ul></div>'
            )
        if step.actual_outputs:
            items = "".join(
                f"<li><code>{escape(a)}</code></li>" for a in step.actual_outputs
            )
            rows.append(
                f'<div class="plan-step-artifacts">'
                f'<strong>Outputs:</strong><ul>{items}</ul></div>'
            )
        params = getattr(step, "params", None)
        if isinstance(params, dict) and params:
            try:
                params_json = json.dumps(params, indent=2, ensure_ascii=False, default=str)
            except Exception:
                params_json = str(params)
            rows.append(
                '<details class="plan-step-params-export">'
                f"<summary>Parameters ({len(params)})</summary>"
                f"<pre>{escape(params_json)}</pre>"
                "</details>"
            )
        rows.append("</li>")
    rows.append("</ol>")
    rows.append("</section>")
    return "\n".join(rows)


def build_session_markdown(
    messages,
    plan_markdown: str = "",
    title: str = "",
    prompts_snapshot: Optional[Mapping[str, str]] = None,
    plan_doc=None,
) -> str:
    """Build a self-contained markdown document from a chat session.

    Unlike the HTML export, this one is plain prose designed for
    copy/paste into a notebook, paper draft, or issue tracker. No
    avatars, no styles, no sub-agent ReAct scratchpads.

    Args:
        messages: Sequence of LangChain messages from the session.
        plan_markdown: The evolving plan as on-disk markdown. Inlined
            verbatim at the top of the document when non-empty.
        title: Optional session title shown in the heading.
        prompts_snapshot: Optional mapping of agent name to system prompt text,
            appended as a prompts section when non-empty.
        plan_doc: Optional pre-parsed PlanDocument; used to render plan
            provenance without re-parsing plan_markdown.

    Returns:
        A complete markdown string.
    """
    lines: List[str] = []
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_title = f"TissueAgent session — {title}" if title else "TissueAgent session"
    lines.append(f"# {header_title}")
    lines.append("")
    lines.append(f"*Exported {when}*")
    lines.append("")

    if plan_markdown and plan_markdown.strip():
        lines.append("## Plan")
        lines.append("")
        # Pull provenance into a friendly prose line above the plan body
        # so it's visible at a glance, not buried in the YAML frontmatter.
        from server.plan_store import _parse_markdown as _pp
        try:
            _doc = _pp(plan_markdown)
            if _doc.provenance.template_names:
                names = ", ".join(f"`{n}`" for n in _doc.provenance.template_names)
                label = "template" if len(_doc.provenance.template_names) == 1 else "templates"
                line = f"_From {label}: {names}"
            else:
                line = "_De novo plan (no template used)"
            if _doc.provenance.justification:
                line += f" — {_doc.provenance.justification}"
            line += "_"
            lines.append(line)
            lines.append("")
        except Exception:
            pass
        # The on-disk plan markdown already has its own ``# Plan`` heading
        # plus ``## Step N`` subheadings; demote each ``#`` so the export's
        # outline is consistent.
        lines.append(_demote_markdown_headings(plan_markdown, by=1))
        lines.append("")

    # Per-step run parameters — extracted from the conversation post-hoc
    # (not part of the on-disk plan markdown). Only emitted when *plan_doc*
    # was provided and at least one step has params.
    if plan_doc is not None and any(
        isinstance(getattr(s, "params", None), dict) and s.params
        for s in plan_doc.steps
    ):
        lines.append("## Run parameters")
        lines.append("")
        lines.append(
            "_Args the manager passed to each specialist when it ran._"
        )
        lines.append("")
        for step in plan_doc.steps:
            params = getattr(step, "params", None)
            if not isinstance(params, dict) or not params:
                continue
            lines.append(f"### Step {step.id} — {step.title}")
            lines.append("")
            try:
                pj = json.dumps(params, indent=2, ensure_ascii=False, default=str)
            except Exception:
                pj = str(params)
            lines.append("```json")
            lines.append(pj)
            lines.append("```")
            lines.append("")

    lines.append("## Conversation")
    lines.append("")
    for idx, message in enumerate(messages, start=1):
        if isinstance(message, HumanMessage):
            text = stringify_chat_content(message.content).strip()
            if not text:
                continue
            lines.append(f"### {idx}. User")
            lines.append("")
            lines.append(text)
            lines.append("")
        elif isinstance(message, AIMessage):
            text = stringify_chat_content(message.content).strip()
            if not text:
                continue
            _, role_label = lookup_agent_badge(message.name)
            lines.append(f"### {idx}. {role_label}")
            lines.append("")
            route, body = split_route_and_body(text)
            if route:
                lines.append(f"_ROUTE: {route}_")
                lines.append("")
            lines.append(body or text)
            lines.append("")
        elif isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", "") or "tool"
            body = stringify_chat_content(message.content).strip()
            if not body:
                continue
            lines.append(f"### {idx}. Tool — `{tool_name}`")
            lines.append("")
            lines.append("```")
            lines.append(body)
            lines.append("```")
            lines.append("")

    if prompts_snapshot:
        lines.append("## Prompts snapshot")
        lines.append("")
        lines.append(
            "_System prompts as they were when the session was saved._"
        )
        lines.append("")
        for agent_id, text in prompts_snapshot.items():
            lines.append(f"### `{agent_id}`")
            lines.append("")
            lines.append("```")
            lines.append(text)
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _demote_markdown_headings(md: str, *, by: int) -> str:
    """Shift every ATX-style heading by *by* levels (max 6).

    Used so an inlined plan markdown that starts at ``# Plan`` becomes ``## Plan`` inside the export's outline.
    """
    if by <= 0:
        return md

    def shift(match: "re.Match[str]") -> str:
        hashes, rest = match.group(1), match.group(2)
        new = "#" * min(6, len(hashes) + by)
        return f"{new}{rest}"

    return re.sub(r"^(#{1,6})( .*)", shift, md, flags=re.MULTILINE)


def _render_prompts_snapshot_html(snapshot: Mapping[str, str]) -> str:
    """Render a prompts snapshot as a collapsible section.

    Returns an empty string if the snapshot is empty so callers can elide the whole section.
    """
    if not snapshot:
        return ""
    items: List[str] = []
    for agent_id, text in snapshot.items():
        items.append(
            "<details><summary><code>"
            f"{escape(agent_id)}</code></summary>"
            f"<pre>{escape(text)}</pre>"
            "</details>"
        )
    return (
        '<section class="prompts-export">'
        "<h2>Prompts snapshot</h2>"
        "<p style=\"font-size:0.8rem;color:#666;\">System prompts as they "
        "were when the session was saved. Click an entry to expand.</p>"
        + "".join(items)
        + "</section>"
    )


def build_session_html(
    messages,
    subagent_states,
    plan_markdown: str = "",
    prompts_snapshot: Optional[Mapping[str, str]] = None,
    plan_doc=None,
) -> str:
    """Build a self-contained HTML document from a chat session.

    Args:
        messages: Sequence of LangChain messages comprising the session.
        subagent_states: Mapping of tool message IDs to (agent_name, final_state) tuples.
        plan_markdown: The evolving plan as on-disk markdown. Rendered
            as the first block in the export when non-empty.
        prompts_snapshot: Optional mapping of agent name to system prompt text,
            rendered as a collapsible prompts section at the end.
        plan_doc: Optional pre-parsed PlanDocument; used to render plan
            provenance without re-parsing plan_markdown.

    Returns:
        A complete HTML string.
    """
    plan_html = _render_plan_html(plan_markdown, plan_doc=plan_doc)
    prompts_html = _render_prompts_snapshot_html(prompts_snapshot or {})
    rendered_blocks = _render_conversation_history_html(messages, subagent_states)
    return "\n".join(
        [
            "<html>",
            "<head>",
            '<meta charset="utf-8" />',
            "<title>TissueAgent Session Export</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;"
            " margin: 2rem; max-width: 1100px; }",
            "h1 { font-size: 1.5rem; }",
            "h2 { margin-top: 2rem; }",
            ".message { margin-bottom: 1.5rem; padding: 1rem; border-radius: 0.75rem; border: 1px solid #e0e0e0; }",
            ".role-user { background-color: #f0f4ff; }",
            ".role-ai { background-color: #f4fff0; }",
            ".role-tool { background-color: #fffaf0; }",
            ".message h3 { margin-top: 0; margin-bottom: 0.5rem; }",
            ".message p { margin: 0.3rem 0; }",
            (
                ".subagent-block { background-color: #ffffff;"
                " border: 1px dashed #d0d0d0; padding: 0.75rem;"
                " border-radius: 0.5rem; margin-top: 0.5rem; }"
            ),
            ".subagent-block h4 { margin: 0 0 0.35rem 0; }",
            (
                ".route-pill { display: inline-block;"
                " padding: 0.2rem 0.6rem; border-radius: 999px;"
                " background: #e0e7ff; color: #1f2a44;"
                " font-size: 0.85rem; margin-top: 0.4rem; }"
            ),
            (
                ".tag-label { font-weight: 600;"
                " text-transform: capitalize;"
                " display: block; margin-top: 0.4rem; }"
            ),
            (
                "pre { white-space: pre-wrap; word-break: break-word;"
                " background: #fafafa; padding: 0.5rem;"
                " border-radius: 0.4rem; border: 1px solid #e3e3e3; }"
            ),
            # Plan-export styles
            (
                ".plan-export { background: #fafbff; border: 1px solid #d0d7ff;"
                " border-radius: 0.75rem; padding: 1rem 1.25rem; margin-bottom: 2rem; }"
            ),
            ".plan-export h2 { margin-top: 0; }",
            ".plan-meta { margin-bottom: 0.5rem; }",
            (
                ".plan-status-pill { display: inline-block; padding: 0.15rem 0.55rem;"
                " border-radius: 999px; font-size: 0.75rem;"
                " background: #e0e7ff; color: #1f2a44; font-weight: 600; }"
            ),
            ".plan-status-done, .plan-status-recruited { background: #d6f5d6; color: #1f4d1f; }",
            ".plan-status-failed { background: #ffe0e0; color: #6b1f1f; }",
            ".plan-status-running { background: #fff3cd; color: #5a4500; }",
            (
                ".plan-edited { display: inline-block; margin-left: 0.4rem;"
                " padding: 0.05rem 0.4rem; font-size: 0.7rem; font-weight: 600;"
                " background: #fef3c7; color: #7a4e00; border-radius: 0.35rem; }"
            ),
            ".plan-provenance-line { font-size: 0.8rem; color: #555; font-style: italic; margin: 0.2rem 0 0.5rem; }",
            ".plan-request { font-size: 0.9rem; margin-bottom: 0.8rem; }",
            ".plan-steps { padding-left: 1.25rem; }",
            ".plan-step { margin: 0.6rem 0; padding-bottom: 0.6rem; border-bottom: 1px solid #eaeaea; }",
            ".plan-step:last-child { border-bottom: none; }",
            ".plan-step-head { font-weight: 600; margin-bottom: 0.3rem; }",
            ".plan-step-num { color: #6b7280; margin-right: 0.4rem; }",
            (
                ".plan-step-badge { display: inline-block; margin-left: 0.4rem;"
                " padding: 0.05rem 0.4rem; font-size: 0.7rem; font-weight: 600;"
                " border-radius: 0.35rem; background: #e5e7eb; color: #374151; }"
            ),
            ".plan-step-artifacts { font-size: 0.85rem; }",
            ".plan-step-artifacts ul { margin: 0.2rem 0 0.5rem 1rem; padding: 0; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>TissueAgent Session Export — {escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</h1>",
            plan_html,
            "<h2>Conversation</h2>",
            rendered_blocks,
            prompts_html,
            "</body>",
            "</html>",
        ]
    )
