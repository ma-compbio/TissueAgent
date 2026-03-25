"""Global session state manager replacing Streamlit's session_state.

Provides a single-user in-memory session that holds the agent graph,
message history, sub-agent states, file upload metadata, and the
thread-safe queues used for real-time UI streaming.
"""

import threading
from collections import deque
from queue import Queue
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from langgraph.graph.state import CompiledStateGraph

from server.utils import message_identity, should_hide_message


class SessionState:
    """Thread-safe, single-user session state container."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Agent graph (set once at startup)
        self.agent: Optional[CompiledStateGraph] = None

        # Core conversation state
        self.agent_state: Dict[str, Any] = {
            "messages": [],
            "replan_count": 0,
            "replan_history": [],
        }

        # Sub-agent tracking
        self.subagent_states: Dict[str, Tuple[str, Any]] = {}
        self.pending_subagent_states: Deque[Any] = deque()

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
