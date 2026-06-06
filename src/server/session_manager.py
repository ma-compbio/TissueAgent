"""Global session state manager replacing Streamlit's session_state.

Provides a single-user in-memory session that holds the agent graph,
message history, sub-agent states, file upload metadata, and the
thread-safe queues used for real-time UI streaming.
"""

import threading
import uuid
from collections import deque
from queue import Queue
from typing import Any, Deque, Dict, List, Literal, Optional, Set, Tuple

from langgraph.graph.state import CompiledStateGraph

from server.utils import message_identity, should_hide_message


SessionMode = Literal["autopilot", "copilot"]


def _new_thread_id() -> str:
    """Generate a fresh LangGraph thread_id for a single user turn."""
    return uuid.uuid4().hex


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

    def reset(self) -> None:
        """Reset the session to a clean state (preserves agent graph)."""
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
            self.ui_event_queue = Queue()
            self.state_queue = Queue()
            self.is_running = False
            self.thread_id = _new_thread_id()
            self.paused_at = None
            self.gates_fired = set()

    def ensure_display_state(self) -> None:
        """Synchronise display_messages with the canonical agent message list."""
        existing = [
            msg for msg in self.agent_state["messages"] if not should_hide_message(msg)
        ]
        self.display_messages = existing
        self.display_message_ids = set(message_identity(msg) for msg in existing)

    def append_display_message(self, message: Any) -> bool:
        """Append *message* to the display list if it is new. Returns True if added."""
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
