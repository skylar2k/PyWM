"""Reading the displays.

Geometry comes from CoreGraphics, *every time we ask*. `NSScreen` is only
consulted for two things CoreGraphics cannot tell us: the display's name and
its *usable area* (`visibleFrame`, which excludes the menu bar and Dock).

Why not use `NSScreen` for everything? In a process that has no running
NSApplication, `NSScreen.screens()` can hand back a stale snapshot taken at the
first call. CoreGraphics is queried live, and its coordinates (`CGDisplayBounds`)
are already top-left based, i.e. the same as AX. Only `visibleFrame` is in AppKit's
bottom-left space, so it goes through `flip_y`. If AppKit's answer is missing
or implausible (not inside the display it claims to describe), we fall back to
the full frame rather than trust it.
"""

import logging

from AppKit import NSScreen
from Quartz import CGDisplayBounds, CGGetActiveDisplayList, CGMainDisplayID

from pywm.core.types import Screen
from pywm.geometry import Rect, flip_y

log = logging.getLogger(__name__)

MAX_DISPLAYS = 32


def _rect(cg_rect) -> Rect:
    return Rect.from_floats(cg_rect.origin.x, cg_rect.origin.y, cg_rect.size.width, cg_rect.size.height)


def _appkit_details(primary_height: int) -> dict[int, tuple[str, Rect]]:
    """display id -> (name, usable area in AX coordinates), using AppKit only for these."""
    details: dict[int, tuple[str, Rect]] = {}
    try:
        for s in NSScreen.screens():
            display_id = int(s.deviceDescription()["NSScreenNumber"])
            vf = s.visibleFrame()
            visible = Rect.from_floats(vf.origin.x, vf.origin.y, vf.size.width, vf.size.height)
            details[display_id] = (str(s.localizedName()), flip_y(visible, primary_height))
    except Exception:  # AppKit trouble must never take down geometry
        log.debug("NSScreen unavailable; using full display frames", exc_info=True)
    return details


def read_screens() -> list[Screen]:
    err, ids, count = CGGetActiveDisplayList(MAX_DISPLAYS, None, None)
    if err != 0 or not count:
        return []
    primary_height = round(CGDisplayBounds(CGMainDisplayID()).size.height)
    details = _appkit_details(primary_height)
    screens = []
    for display_id in ids[:count]:
        frame = _rect(CGDisplayBounds(display_id))
        name, work = details.get(display_id, (f"Display {display_id}", frame))
        if work.overlap_area(frame) != work.w * work.h:  # not inside its own display: stale or bogus
            work = frame
        screens.append(Screen(int(display_id), name, frame, work))
    return screens
