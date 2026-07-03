"""Global session state manager replacing Streamlit's session_state.

Provides a single-user in-memory session that holds the agent graph, message history, sub-agent states, file upload
metadata, and the thread-safe queues used for real-time UI streaming.
"""

import threading
import uuid
from collections import deque
from datetime import datetime
from queue import Queue
from typing import Any, Deque, Dict, List, Literal, Optional, Set, Tuple

from langgraph.graph.state import CompiledStateGraph

from server.utils import message_identity, should_hide_message


SessionMode = Literal["autopilot", "copilot"]


def _new_thread_id() -> str:
    """Generate a fresh LangGraph thread_id for a single user turn."""
    return uuid.uuid4().hex


def _new_thread_id_for_project() -> str:
    """Mint a stable, human-readable id for a freshly-started project.

    Doubles as the on-disk folder name under ``projects/``. Timestamp
    is enough since this is a local single-user app.
    """
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class SessionState:
    """Thread-safe, single-user session state container."""

    def __init__(self) -> None:
        """Initialise an empty session with default values."""
        self._lock = threading.Lock()

        # Agent graph (compiled at startup, recompiled when model selection changes)
        self.agent: Optional[CompiledStateGraph] = None
        self.model_revision: Optional[int] = None

        # Execution mode. autopilot = no pauses; copilot = pause for human
        # review after planner and after recruiter. Default autopilot so
        # non-app entry points (notebook, CLI) never pause.
        self.mode: SessionMode = "autopilot"

        # LangGraph thread_id for the *current* user turn. Refreshed at
        # the start of each new query so checkpointer state from earlier
        # interrupts can't be confused with a fresh run. The checkpointer
        # itself is attached to ``self.agent`` at compile time.
        self.thread_id: str = _new_thread_id()

        # Set when a copilot run pauses at an interrupt; cleared on
        # resume or new turn. None ⇒ no pause is active.
        self.paused_at: Optional[str] = None

        # LangGraph's ``interrupt_before`` is sticky — once a node is in
        # the list, the graph pauses *every* time it's about to enter
        # that node, including inner-loop returns (e.g. manager_tools →
        # manager_agent). We want each gate to fire **at most once** per
        # turn. Track which gates have already fired so we can drop them
        # from ``interrupt_before`` on subsequent resumes.
        self.gates_fired: Set[str] = set()

        # Persistent project identifier for the current conversation.
        # Assigned on the first user prompt (or first upload) and reused
        # on subsequent messages so the project file is updated in place
        # rather than re-created. ``None`` ⇒ no project is active (fresh
        # session or post-clear).
        self.project_id: Optional[str] = None
        self.project_title: str = ""

        # Core conversation state
        self.agent_state: Dict[str, Any] = {
            "messages": [],
            "replan_count": 0,
            "replan_history": [],
            "recruiter_retry_count": 0,
        }

        # Sub-agent tracking: {tool_id: (agent_name, state, invocation_id)}
        self.subagent_states: Dict[str, Tuple[str, Any, Optional[str]]] = {}
        self.pending_subagent_states: Deque[Tuple[str, Any, Optional[str]]] = deque()

        # Display deduplication
        self.display_messages: List[Any] = []
        self.display_message_ids: Set[str] = set()

        # File upload metadata
        self.pending_images: List[Dict[str, str]] = []
        self.uploaded_pdfs: List[Dict[str, Any]] = []
        self.processed_files: Set[str] = set()

        # Thread-safe queues for real-time streaming
        self.ui_event_queue: Queue = Queue()
        self.state_queue: Queue = Queue()

        # Prevents concurrent agent invocations
        self.is_running: bool = False

    def ensure_project_id(self) -> str:
        """Mint a project id if none is active, then return it.

        This lives on the session rather than in any one route handler
        because chat *and* file-upload both need to be able to bind the
        current conversation to an on-disk project folder. Whichever
        happens first wins; both paths read the same id afterwards.
        """
        if not self.project_id:
            self.project_id = _new_thread_id_for_project()
        return self.project_id

    def reset(self) -> None:
        """Reset the session to a clean state (preserves agent graph).

        IMPORTANT: ``ui_event_queue`` and ``state_queue`` are *drained in
        place*, not replaced. The compiled graph and ``graph_utils``
        captured references to the original queue objects at startup; if
        we swapped them out for fresh ``Queue()`` instances, agent
        output would land in the orphaned originals and never reach the
        WebSocket, leaving the user staring at silence after every
        "new project" click.
        """
        with self._lock:
            self.agent_state = {
                "messages": [],
                "replan_count": 0,
                "replan_history": [],
                "recruiter_retry_count": 0,
            }
            self.subagent_states = {}
            self.pending_subagent_states = deque()
            self.display_messages = []
            self.display_message_ids = set()
            self.pending_images = []
            self.uploaded_pdfs = []
            self.processed_files = set()
            while not self.ui_event_queue.empty():
                try:
                    self.ui_event_queue.get_nowait()
                except Exception:
                    break
            while not self.state_queue.empty():
                try:
                    self.state_queue.get_nowait()
                except Exception:
                    break
            self.is_running = False
            self.thread_id = _new_thread_id()
            self.paused_at = None
            self.gates_fired = set()
            # project_id / project_title are cleared by switch_active_project
            # below — leaving them set here would lie about on-disk state.

        # Park the active project (if any) and reset workspace/project/ to
        # an empty shell. Outside the lock — touches disk and the kernel
        # client, which shouldn't be holding the session lock.
        try:
            from server.utils import switch_active_project
            switch_active_project(None)
        except Exception:
            # Best-effort; never let workspace cleanup break a reset.
            pass

        # Reset accumulated API usage metrics — a new project starts clean.
        from server.usage_tracker import usage_tracker
        usage_tracker.reset()

    def ensure_display_state(self) -> None:
        """Synchronise display_messages with the canonical agent message list."""
        existing = [
            msg for msg in self.agent_state["messages"] if not should_hide_message(msg)
        ]
        self.display_messages = existing
        self.display_message_ids = set(message_identity(msg) for msg in existing)

    def append_display_message(self, message: Any) -> bool:
        """Append *message* to the display list if it is new.

        Returns True if added.
        """
        if should_hide_message(message):
            return False
        msg_key = message_identity(message)
        if msg_key in self.display_message_ids:
            return False
        self.display_message_ids.add(msg_key)
        self.display_messages.append(message)
        return True


# Global singleton instance
session = SessionState()
