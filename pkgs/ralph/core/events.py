"""Structured events emitted by Ralph's lifecycle.

EventBus bridges the sync Ralph Loop thread and the async FastAPI server.
The loop calls ``bus.emit()``; the server drains events via ``bus.drain()``.
"""

import queue
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """All lifecycle event types emitted by the Ralph Loop."""

    LOOP_STARTED = "loop_started"
    LOOP_STOPPED = "loop_stopped"
    LOOP_WAITING = "loop_waiting"
    ITER_STARTED = "iter_started"
    ITER_COMPLETED = "iter_completed"
    ITER_FAILED = "iter_failed"
    AGENT_OUTPUT = "agent_output"
    AGENT_STATUS = "agent_status"
    TASK_CLAIMED = "task_claimed"
    TASK_DONE = "task_done"
    TASK_BLOCKED = "task_blocked"
    TASK_HELP = "task_help"
    RESOURCE_CHECK = "resource_check"
    TAG_CREATED = "tag_created"
    ROLLBACK = "rollback"
    VALIDATION_FAILED = "validation_failed"
    # loop observability
    LOOP_HEARTBEAT = "loop_heartbeat"
    LOOP_STALLED = "loop_stalled"
    TASK_PROGRESS = "task_progress"
    # git push
    GIT_PUSH_SUCCESS = "git_push_success"
    GIT_PUSH_FAILED = "git_push_failed"
    # diff
    TASK_DIFF = "task_diff"
    # task CRUD (emitted from API endpoints)
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_DELETED = "task_deleted"


@dataclass
class Event:
    """A single lifecycle event with type, timestamp, and context data."""

    type: EventType
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "timestamp": self.timestamp, "data": self.data}


class EventBus:
    """Thread-safe event bus. Ralph Loop (sync) pushes, FastAPI (async) consumes."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: queue.Queue[Event] = queue.Queue(maxsize=maxsize)
        self._callbacks: list[Callable[[Event], None]] = []

    def emit(self, event: Event) -> None:
        """Enqueue an event (called from the sync loop thread)."""
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            pass  # drop oldest-style: consumer should drain faster
        for cb in self._callbacks:
            cb(event)

    def on(self, callback: Callable[[Event], None]) -> None:
        """Register a synchronous callback (e.g. for logging)."""
        self._callbacks.append(callback)

    def drain(self) -> list[Event]:
        """Non-blocking drain of all queued events (called by the server)."""
        events: list[Event] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events
