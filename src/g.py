import threading
from typing import Any

# Simple thread-local wrapper to emulate flask_g
_local = threading.local()

class _GLocals:
    def __getattr__(self, name: str) -> Any:
        return getattr(_local, name, None)
    
    def __setattr__(self, name: str, value: Any) -> None:
        setattr(_local, name, value)

g = _GLocals()
