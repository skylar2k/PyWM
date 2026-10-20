"""`Bar`: a small indicator panel per monitor, redrawn whenever the window manager says so.

The window manager decides the *band* the bar occupies (`MonitorStatus.bar_rect`: the very top of the
display, as tall as the menu bar / notch area it covers). This package decides what is drawn inside
that band: a compact indicator, just wide enough for the tags and the layout symbol, starting at the
right edge of the notch. The rest of the menu bar stays untouched and usable.

The panel is click-through and non-activating, so it never steals focus or swallows clicks.
"""

import math
from dataclasses import dataclass
from types import ModuleType

from AppKit import (
    NSBackingStoreBuffered,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSMakeRect
from Quartz import CGDisplayBounds, CGMainDisplayID

from pywm.bar.view import BarView, content_width, make_view
from pywm.core.wm import MonitorStatus
from pywm.geometry import Rect, flip_y


def compact_frame(band: Rect, content_w: float, anchor_x: int) -> Rect:
    """The indicator's frame: it starts at `anchor_x`, is as wide as its content, and fills the
    band vertically. It is pulled back if it would run past the band's right edge."""
    w = min(math.ceil(content_w), band.w)
    x = max(band.x, min(anchor_x, band.right - w))
    return Rect(x, band.y, w, band.h)


def notch_right_edge(display_id: int, band: Rect) -> int | None:
    """The x coordinate where the notch ends, or None if this display has no notch.

    `band` is the full-width strip at the top of the display; only its horizontal extent is used.
    Monitor ids are CoreGraphics display ids, which is also what NSScreen reports as its number.
    """
    for screen in NSScreen.screens():
        if int(screen.deviceDescription()["NSScreenNumber"]) != display_id:
            continue
        area = screen.auxiliaryTopRightArea()  # the usable strip to the right of the notch
        if area.size.width <= 0:
            return None
        x = round(area.origin.x)
        if not band.x <= x <= band.right:  # given in the screen's own coordinates: make it global
            x += band.x
        return x
    return None


@dataclass(slots=True)
class _Panel:
    window: NSPanel
    view: BarView
    band: Rect  # the full-width band last given by the window manager
    anchor: int  # where the indicator starts (notch edge, or screen centre without a notch)
    frame: Rect | None = None  # where the panel currently is (AX coordinates)


class Bar:
    def __init__(self, config: ModuleType) -> None:
        self._font_size = config.BAR_FONT_SIZE
        self._colors = config.COLORS
        self._panels: dict[int, _Panel] = {}  # monitor id -> panel

    def update(self, statuses: list[MonitorStatus]) -> None:
        """Subscribe this to `wm.changed`."""
        wanted = {s.monitor: s for s in statuses if s.bar_rect is not None}
        for monitor in self._panels.keys() - wanted.keys():  # bar toggled off on that monitor
            self._panels.pop(monitor).window.orderOut_(None)
        primary_height = round(CGDisplayBounds(CGMainDisplayID()).size.height)  # read live, never cached
        for monitor, status in wanted.items():
            band = status.bar_rect
            assert band is not None
            panel = self._panels.get(monitor)
            is_new = panel is None
            if panel is None:
                window, view = self._make_panel()
                panel = self._panels[monitor] = _Panel(window, view, band, self._anchor(monitor, band))
            elif band != panel.band:  # display changed: the notch may have moved
                panel.band, panel.anchor = band, self._anchor(monitor, band)
            if panel.view.status != status:
                panel.view.status = status
                panel.view.setNeedsDisplay_(True)
            # The indicator's width follows its content (the layout symbol changes width).
            frame = compact_frame(panel.band, content_width(panel.view.font, status), panel.anchor)
            if frame != panel.frame:
                panel.frame = frame
                panel.window.setFrame_display_(self._appkit_rect(frame, primary_height), True)
                panel.view.setFrameSize_((frame.w, frame.h))
            if is_new:  # show it only once it has its final size and position
                panel.window.orderFrontRegardless()

    def close(self) -> None:
        for panel in self._panels.values():
            panel.window.orderOut_(None)
        self._panels.clear()

    @staticmethod
    def _anchor(monitor: int, band: Rect) -> int:
        """Right of the notch; on a display without one, where the notch would be (the centre)."""
        edge = notch_right_edge(monitor, band)
        return edge if edge is not None else band.x + band.w // 2

    @staticmethod
    def _appkit_rect(rect: Rect, primary_height: int):
        f = flip_y(rect, primary_height)  # AX coordinates -> AppKit coordinates
        return NSMakeRect(f.x, f.y, f.w, f.h)

    def _make_panel(self):
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 1, 1), style, NSBackingStoreBuffered, False
        )
        window.setLevel_(NSStatusWindowLevel)  # above normal windows, and above the menu bar
        window.setIgnoresMouseEvents_(True)  # clicks fall through to whatever is underneath
        window.setHasShadow_(False)
        window.setReleasedWhenClosed_(False)
        window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        view = make_view(1, 1, self._font_size, self._colors)
        window.setContentView_(view)
        return window, view
