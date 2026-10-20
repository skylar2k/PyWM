"""The boundary between the window manager and an operating system.

`Platform` is the Adapter/Facade (*Software Design for Python Programmers*,
ch. 10) that hides everything macOS-specific behind a handful of methods. The
controller only ever sees this protocol, so tests can plug in `FakePlatform`
and a port to another OS would only have to implement it.

A `Protocol` (*Fluent Python*, ch. 13) is "static duck typing": classes satisfy
it by having the right methods; none of them has to inherit from it.
"""

from collections.abc import Callable
from typing import Protocol

from pywm.core.keys import Chord
from pywm.core.types import Screen, WindowId, WindowInfo
from pywm.geometry import Rect
from pywm.platform.events import Event


class Platform(Protocol):
    # --- reading the world ---
    def screens(self) -> list[Screen]: ...
    def app_pids(self) -> list[int]:
        """Processes that may own windows we care about."""
        ...

    def window_infos(self, pid: int) -> list[WindowInfo] | None:
        """A snapshot of one app's windows, or None if the app could not be queried (hung)."""
        ...

    def window_exists(self, wid: WindowId) -> bool: ...
    def focused_window(self) -> WindowId | None: ...

    # --- changing the world ---
    def set_frame(self, wid: WindowId, rect: Rect) -> Rect | None:
        """Move/resize a window; return the frame it *actually* ended up with."""
        ...

    def hide(self, wid: WindowId) -> None: ...
    def show(self, wid: WindowId) -> None:
        """Undo `hide`: put the window back where it was. No-op if it is not hidden."""
        ...

    def focus(self, wid: WindowId) -> None: ...
    def raise_window(self, wid: WindowId) -> None: ...
    def close(self, wid: WindowId) -> None: ...
    def spawn(self, argv: tuple[str, ...]) -> None: ...
    def restore_all(self) -> None:
        """Bring every hidden window back. Called on the way out."""
        ...

    # --- plumbing ---
    def grab_keys(self, chords: set[Chord], on_chord: Callable[[Chord], None]) -> None: ...
    def call_later(self, delay: float, fn: Callable[[], None]) -> None: ...
    def run(self, on_event: Callable[[Event], None]) -> None:
        """Start watching for events and block until `stop()`."""
        ...

    def stop(self) -> None: ...
