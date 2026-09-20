from enum import Enum, auto
from PyQt6.QtCore import QObject, pyqtSignal
from .logger import Logger


class GuardState(Enum):
    IDLE = auto()
    ACTIVE = auto()
    PROTECTED = auto()
    SHARING = auto()
    PAUSED = auto()
    ERROR = auto()


_VALID_TRANSITIONS: dict[GuardState, set[GuardState]] = {
    GuardState.IDLE: {GuardState.ACTIVE, GuardState.ERROR},
    GuardState.ACTIVE: {GuardState.PROTECTED, GuardState.PAUSED, GuardState.IDLE, GuardState.ERROR},
    GuardState.PROTECTED: {GuardState.ACTIVE, GuardState.SHARING, GuardState.IDLE, GuardState.ERROR},
    GuardState.SHARING: {GuardState.ACTIVE, GuardState.PROTECTED, GuardState.IDLE, GuardState.ERROR},
    GuardState.PAUSED: {GuardState.ACTIVE, GuardState.IDLE, GuardState.ERROR},
    GuardState.ERROR: {GuardState.IDLE},
}


class StateMachine(QObject):
    state_changed = pyqtSignal(object, object)  # (old_state, new_state)

    def __init__(self) -> None:
        super().__init__()
        self._state = GuardState.IDLE
        self._log = Logger.get()

    @property
    def state(self) -> GuardState:
        return self._state

    def transition_to(self, new_state: GuardState) -> bool:
        if new_state == self._state:
            return True
        valid = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in valid:
            self._log.warning(
                f"Invalid transition: {self._state.name} -> {new_state.name}"
            )
            return False
        old = self._state
        self._state = new_state
        self._log.debug(f"State: {old.name} -> {new_state.name}")
        self.state_changed.emit(old, new_state)
        return True

    def reset(self) -> None:
        old = self._state
        self._state = GuardState.IDLE
        if old != GuardState.IDLE:
            self.state_changed.emit(old, GuardState.IDLE)

    def is_active(self) -> bool:
        return self._state in (GuardState.ACTIVE, GuardState.PROTECTED, GuardState.SHARING)
