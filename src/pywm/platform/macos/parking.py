"""Where hidden windows go.

macOS has no "hide just this window" call (minimizing animates and clutters the Dock; hiding an
app hides *all* its windows). So, like AeroSpace, we *park* windows at the bottom-right corner of
the desktop, just out of sight, remember where they were, and move them back when their tag is
shown again.

The risk is a crash while windows are parked. Normal exits (including Ctrl-C and SIGTERM) restore
them. After a hard kill they sit in the corner, but the next start of pywm adopts every window it
can see and tiles it back onto the screen, so nothing is permanently lost.
"""

from pywm.core.types import Screen, WindowId
from pywm.geometry import Rect, union


def corner(screens: list[Screen]) -> tuple[int, int]:
    """The point just inside the bottom-right of the combined desktop."""
    desktop = union([s.frame for s in screens])
    return desktop.right - 1, desktop.bottom - 1


class Parking:
    """Remembers the real frame of every parked window."""

    def __init__(self) -> None:
        self.frames: dict[WindowId, Rect] = {}

    def __contains__(self, wid: WindowId) -> bool:
        return wid in self.frames

    def park(self, wid: WindowId, original: Rect) -> None:
        self.frames[wid] = original

    def unpark(self, wid: WindowId) -> Rect | None:
        return self.frames.pop(wid, None)
