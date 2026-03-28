import threading
from contextlib import contextmanager
from typing import Any

# Simple thread-local wrapper to emulate flask_g
_local = threading.local()
_MISSING = object()
_shared_scenario_run = None

class _GLocals:
    def __getattr__(self, name: str) -> Any:
        value = getattr(_local, name, _MISSING)
        if value is not _MISSING:
            return value
        if name == "scenario_run":
            return _shared_scenario_run
        return None
    
    def __setattr__(self, name: str, value: Any) -> None:
        setattr(_local, name, value)


@contextmanager
def bind_shared_scenario_run(scenario_run: Any):
    """Expose the active scenario to worker threads during a single request."""
    global _shared_scenario_run

    previous_local = getattr(_local, "scenario_run", _MISSING)
    previous_shared = _shared_scenario_run
    _shared_scenario_run = scenario_run
    setattr(_local, "scenario_run", scenario_run)
    try:
        yield
    finally:
        _shared_scenario_run = previous_shared
        if previous_local is _MISSING:
            try:
                delattr(_local, "scenario_run")
            except AttributeError:
                pass
        else:
            setattr(_local, "scenario_run", previous_local)


g = _GLocals()
