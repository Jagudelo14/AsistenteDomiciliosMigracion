import contextvars
from typing import Optional

_sender_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sender", default=None)

def set_sender(sender: str) -> None:
    _sender_var.set(sender)

def get_sender() -> Optional[str]:
    return _sender_var.get()