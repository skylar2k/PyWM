"""A tiny Observer implementation (see *Software Design for Python Programmers*, ch. 12)."""

from collections.abc import Callable


class Signal[**P]:
    """Subscribers register with `connect`; the publisher calls `emit`.

    The window manager emits `changed` after every re-arrange. The status bar
    subscribes; the WM neither knows nor cares that a bar exists.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callable[P, None]] = []

    def connect(self, fn: Callable[P, None]) -> Callable[P, None]:
        self._subscribers.append(fn)
        return fn

    def disconnect(self, fn: Callable[P, None]) -> None:
        self._subscribers.remove(fn)

    def emit(self, *args: P.args, **kwargs: P.kwargs) -> None:
        for fn in list(self._subscribers):
            fn(*args, **kwargs)
