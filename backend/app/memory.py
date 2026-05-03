import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

# Simple in-memory session storage
# In production, replace with Redis for persistence across restarts
_session_store: dict[str, "ConversationSession"] = {}
_session_lock = asyncio.Lock()
DEFAULT_HISTORY_LIMIT = 10  # Keep last 10 message pairs


@dataclass
class Message:
    """Single message in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationSession:
    """Conversation history for a session."""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    last_entity: Optional[str] = None  # Last mentioned entity (e.g., "Harry", "the spell")
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str) -> None:
        """Add a message and update last entity if it's a user message."""
        self.messages.append(Message(role=role, content=content))
        if role == "user":
            self._extract_entity(content)
        self.last_accessed = time.time()

    def _extract_entity(self, text: str) -> None:
        """Extract likely entities from user message for follow-up tracking."""
        text_lower = text.lower()
        # Simple keyword-based entity extraction
        # Could be enhanced with NER in production
        entity_keywords = [
            "harry", "voldemort", "dumbledore", "snape", "hermione", "ron",
            "spell", "curse", "potion", "house", "wand", "horcrux",
            "the boy who lived", "the dark lord", "the half-blood prince",
        ]
        for keyword in entity_keywords:
            if keyword in text_lower:
                # Extract the relevant phrase
                self.last_entity = text
                return

    def get_context(self, limit: int = DEFAULT_HISTORY_LIMIT) -> str:
        """Get conversation context as a string for injection into prompts."""
        if not self.messages:
            return ""
        
        recent = self.messages[-limit:]
        lines = []
        for msg in recent:
            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role_label}: {msg.content}")
        
        return "\n".join(lines)

    def get_last_entity(self) -> Optional[str]:
        """Get the last mentioned entity for follow-up resolution."""
        return self.last_entity

    def clear(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
        self.last_entity = None


async def get_session(session_id: str) -> ConversationSession:
    """Get or create a session."""
    async with _session_lock:
        if session_id not in _session_store:
            _session_store[session_id] = ConversationSession(session_id=session_id)
        return _session_store[session_id]


async def add_to_session(session_id: str, query: str, answer: str) -> None:
    """Add a query-answer pair to session history."""
    session = await get_session(session_id)
    session.add_message("user", query)
    session.add_message("assistant", answer)
    
    # Sliding window - trim old messages if exceeding limit
    # We keep pairs (user + assistant), so 2x limit
    max_messages = DEFAULT_HISTORY_LIMIT * 2
    if len(session.messages) > max_messages:
        session.messages = session.messages[-max_messages:]


async def get_context_string(session_id: str, limit: int = DEFAULT_HISTORY_LIMIT) -> str:
    """Get formatted context string for a session."""
    session = await get_session(session_id)
    return session.get_context(limit)


async def get_last_entity(session_id: str) -> Optional[str]:
    """Get the last mentioned entity."""
    session = await get_session(session_id)
    return session.get_last_entity()


async def clear_session(session_id: str) -> None:
    """Clear a session's history."""
    session = await get_session(session_id)
    session.clear()


async def cleanup_old_sessions(max_age_seconds: int = 3600) -> int:
    """Remove sessions older than max_age_seconds. Returns count removed."""
    now = time.time()
    to_remove = []
    async with _session_lock:
        for sid, session in _session_store.items():
            if now - session.last_accessed > max_age_seconds:
                to_remove.append(sid)
        for sid in to_remove:
            del _session_store[sid]
    return len(to_remove)


# Start background cleanup task
async def _start_cleanup_task():
    """Background task to clean old sessions."""
    while True:
        await asyncio.sleep(300)  # Run every 5 minutes
        try:
            await cleanup_old_sessions()
        except Exception:
            pass  # Non-critical, don't crash

# Note: To start this, call `_start_cleanup_task()` in application startup