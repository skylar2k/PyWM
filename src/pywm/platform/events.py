"""Events a platform adapter reports to the controller.

They are deliberately *coarse*: "something changed in app X". The controller
answers by asking for a fresh snapshot, so adapters never have to be smart.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppLaunched:
    pid: int


@dataclass(frozen=True, slots=True)
class AppTerminated:
    pid: int


@dataclass(frozen=True, slots=True)
class WindowsChanged:
    """A window of this app was created, destroyed, minimized, resized, ..."""

    pid: int


@dataclass(frozen=True, slots=True)
class WindowsMoved: ...


@dataclass(frozen=True, slots=True)
class FocusChanged: ...


@dataclass(frozen=True, slots=True)
class ScreensChanged:
    """Displays were (un)plugged or rearranged, or the Space changed."""


type Event = AppLaunched | AppTerminated | WindowsChanged | FocusChanged | ScreensChanged | WindowsMoved
