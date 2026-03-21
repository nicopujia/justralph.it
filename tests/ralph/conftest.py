import time
from pathlib import Path

import pytest

from ralph.config import Config
from ralph.core.events import Event, EventBus, EventType


class EventBusAssertions:
    """EventBus wrapper with assertion helpers for tests."""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.received: list[Event] = []
        bus.on(lambda e: self.received.append(e))

    def assert_emitted(self, event_type: EventType, **data_subset: object) -> None:
        matching = [e for e in self.received if e.type == event_type]
        assert matching, f"No {event_type} event emitted"
        if data_subset:
            for e in matching:
                if all(e.data.get(k) == v for k, v in data_subset.items()):
                    return
            assert False, f"No {event_type} event with data {data_subset}"

    def assert_not_emitted(self, event_type: EventType) -> None:
        matching = [e for e in self.received if e.type == event_type]
        assert not matching, f"Unexpected {event_type} event emitted"


@pytest.fixture
def mock_event_bus() -> EventBus:
    """Fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def event_bus_with_assertions() -> EventBusAssertions:
    """EventBus wrapped with assertion helpers."""
    return EventBusAssertions(EventBus())


@pytest.fixture
def sample_events() -> dict[str, Event]:
    """Pre-built Event objects for each EventType."""
    now = time.time()
    return {
        "loop_started": Event(EventType.LOOP_STARTED, now, {}),
        "loop_stopped": Event(EventType.LOOP_STOPPED, now, {"iterations": 5}),
        "loop_waiting": Event(EventType.LOOP_WAITING, now, {}),
        "iter_started": Event(EventType.ITER_STARTED, now, {"task_id": "task-001", "iteration": 0}),
        "iter_completed": Event(EventType.ITER_COMPLETED, now, {"task_id": "task-001"}),
        "iter_failed": Event(EventType.ITER_FAILED, now, {"error": "test error"}),
        "agent_output": Event(EventType.AGENT_OUTPUT, now, {"line": "hello", "task_id": "task-001"}),
        "agent_status": Event(EventType.AGENT_STATUS, now, {"status": "COMPLETED ASSIGNED ISSUE"}),
        "task_claimed": Event(EventType.TASK_CLAIMED, now, {"task_id": "task-001", "title": "Test task"}),
        "task_done": Event(EventType.TASK_DONE, now, {"task_id": "task-001"}),
        "task_blocked": Event(EventType.TASK_BLOCKED, now, {"task_id": "task-001"}),
        "task_help": Event(EventType.TASK_HELP, now, {"task_id": "task-001"}),
        "resource_check": Event(EventType.RESOURCE_CHECK, now, {"cpu": 50.0, "ram": 60.0, "disk": 40.0}),
        "tag_created": Event(EventType.TAG_CREATED, now, {"tag": "pre-iter/task-001/0"}),
        "rollback": Event(EventType.ROLLBACK, now, {"tag": "pre-iter/task-001/0"}),
        "validation_failed": Event(EventType.VALIDATION_FAILED, now, {"reason": "tests failed"}),
    }


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Config with base_dir pointing at tmp dir."""
    return Config(base_dir=tmp_path, log_level="DEBUG")
