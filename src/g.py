import threading
from typing import Any

# Simple thread-local wrapper to emulate flask_g
_local = threading.local()
_shared_state: dict[str, Any] = {"scenario_run": None}

class _GLocals:
    def __getattr__(self, name: str) -> Any:
        if name in _shared_state:
            return _shared_state[name]
        return getattr(_local, name, None)
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name in _shared_state:
            _shared_state[name] = value
            return
        setattr(_local, name, value)

g = _GLocals()
