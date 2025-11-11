import sys
from typing import Optional, Callable

_DEBUG_ENABLED = False

Formatter = Optional[Callable[[str], str]]

def set_debug(enabled: bool) -> None:
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = enabled


def debug_print(message: str, formatter: Formatter = None) -> None:
    if not _DEBUG_ENABLED:
        return
    if formatter:
        message = formatter(message)
    print(message, file=sys.stderr)
