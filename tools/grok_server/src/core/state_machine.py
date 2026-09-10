from enum import Enum, auto
import asyncio
from typing import Callable, List, Optional
from loguru import logger

class ConnectionState(Enum):
    INIT = auto()
    STARTING = auto()
    LOGIN_CHECK = auto()
    READY = auto()
    BUSY = auto()
    WAITING_RESPONSE = auto()
    RECOVERING = auto()
    ERROR = auto()
    PAUSED = auto()  # Waiting for login / credentials

class StateMachineError(Exception):
    pass

class ConnectionStateMachine:
    """
    Finite State Machine for connection lifecycle management.
    """
    # Allowed transitions mapping
    VALID_TRANSITIONS = {
        ConnectionState.INIT: [ConnectionState.STARTING, ConnectionState.ERROR],
        ConnectionState.STARTING: [ConnectionState.LOGIN_CHECK, ConnectionState.ERROR, ConnectionState.RECOVERING, ConnectionState.INIT],
        ConnectionState.LOGIN_CHECK: [ConnectionState.READY, ConnectionState.PAUSED, ConnectionState.RECOVERING, ConnectionState.ERROR],
        ConnectionState.PAUSED: [ConnectionState.LOGIN_CHECK, ConnectionState.STARTING, ConnectionState.RECOVERING, ConnectionState.ERROR, ConnectionState.INIT],
        ConnectionState.READY: [ConnectionState.BUSY, ConnectionState.RECOVERING, ConnectionState.LOGIN_CHECK, ConnectionState.ERROR, ConnectionState.INIT],
        ConnectionState.BUSY: [ConnectionState.WAITING_RESPONSE, ConnectionState.RECOVERING, ConnectionState.ERROR, ConnectionState.READY],
        ConnectionState.WAITING_RESPONSE: [ConnectionState.READY, ConnectionState.RECOVERING, ConnectionState.ERROR, ConnectionState.BUSY],
        ConnectionState.RECOVERING: [ConnectionState.STARTING, ConnectionState.LOGIN_CHECK, ConnectionState.READY, ConnectionState.ERROR],
        ConnectionState.ERROR: [ConnectionState.INIT, ConnectionState.STARTING, ConnectionState.RECOVERING, ConnectionState.READY]
    }

    def __init__(self, initial_state: ConnectionState = ConnectionState.INIT):
        self._state = initial_state
        self._listeners: List[Callable[[ConnectionState, ConnectionState], None]] = []
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ConnectionState:
        return self._state

    def is_ready(self) -> bool:
        return self._state == ConnectionState.READY

    def is_busy(self) -> bool:
        return self._state in (ConnectionState.BUSY, ConnectionState.WAITING_RESPONSE)

    def is_error(self) -> bool:
        return self._state == ConnectionState.ERROR

    def add_listener(self, callback: Callable[[ConnectionState, ConnectionState], None]):
        self._listeners.append(callback)

    async def transition_to(self, new_state: ConnectionState, reason: Optional[str] = None) -> bool:
        async with self._lock:
            old_state = self._state
            if old_state == new_state:
                return True

            allowed = self.VALID_TRANSITIONS.get(old_state, [])
            if new_state not in allowed:
                logger.error(f"[State Machine] Invalid transition: {old_state.name} -> {new_state.name}. Reason: {reason or 'N/A'}")
                raise StateMachineError(f"Cannot transition from {old_state.name} to {new_state.name}")

            self._state = new_state
            logger.info(f"[State Machine] Transition: {old_state.name} -> {new_state.name} | Reason: {reason or 'Normal'}")

            for listener in self._listeners:
                try:
                    if asyncio.iscoroutinefunction(listener):
                        await listener(old_state, new_state)
                    else:
                        listener(old_state, new_state)
                except Exception as e:
                    logger.error(f"[State Machine] Listener error: {e}")

            return True
