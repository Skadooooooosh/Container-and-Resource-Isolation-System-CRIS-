from enum import Enum


class State(str, Enum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


ALLOWED = {
    State.CREATED: {State.STARTING},
    State.STARTING: {State.RUNNING, State.FAILED, State.STOPPING},
    State.RUNNING: {State.STOPPING, State.STOPPED, State.FAILED},
    State.STOPPING: {State.STOPPED, State.FAILED},
    State.STOPPED: {State.STARTING},
    State.FAILED: {State.STARTING},
}
REMOVABLE = {State.CREATED, State.STOPPED, State.FAILED}


def can_transition(a: State, b: State) -> bool:
    return b in ALLOWED.get(a, set())
