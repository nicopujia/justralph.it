"""Simple in-memory SSE event system for pushing events to connected clients."""

import queue
import threading

# slug -> list of queues (one per connected SSE client)
_subscribers: dict[str, list[queue.Queue]] = {}
_lock = threading.Lock()


def subscribe(slug: str) -> queue.Queue:
    """Register a new SSE client for a project. Returns a queue to read events from."""
    q: queue.Queue = queue.Queue()
    with _lock:
        _subscribers.setdefault(slug, []).append(q)
    return q


def unsubscribe(slug: str, q: queue.Queue) -> None:
    """Remove an SSE client's queue."""
    with _lock:
        if slug in _subscribers:
            try:
                _subscribers[slug].remove(q)
            except ValueError:
                pass
            if not _subscribers[slug]:
                del _subscribers[slug]


def publish(slug: str, event_type: str, data: dict) -> None:
    """Push an event to all connected clients for a project."""
    event = {"type": event_type, "data": data}
    with _lock:
        for q in _subscribers.get(slug, []):
            q.put(event)
