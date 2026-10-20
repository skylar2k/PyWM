"""`Bar`: one borderless panel per monitor, redrawn whenever the window manager says so.

The panel is click-through and non-activating, so it never steals focus or swallows clicks. Its
position comes straight from `MonitorStatus.bar_rect`: the window manager decides *where* the
bar goes (it has to, because it also reserves that strip of screen); this package decides what
the bar *looks like*.
"""

from types import ModuleType

from AppKit import (
    NSBackingStoreBuffered,
    NSPanel,
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

from pywm.bar.view import BarView, make_view
from pywm.core.wm import MonitorStatus
from pywm.geometry import Rect, flip_y


class Bar:
    def __init__(self, config: ModuleType) -> None:
        self._font_size = config.BAR_FONT_SIZE
        self._colors = config.COLORS
        self._panels: dict[int, tuple[NSPanel, BarView, Rect]] = {}  # monitor id -> panel

    def update(self, statuses: list[MonitorStatus]) -> None:
        """Subscribe this to `wm.changed`."""
        wanted = {s.monitor: s for s in statuses if s.bar_rect is not None}
        for monitor in self._panels.keys() - wanted.keys():  # bar toggled off on that monitor
            self._panels.pop(monitor)[0].orderOut_(None)
        primary_height = round(CGDisplayBounds(CGMainDisplayID()).size.height)  # read live, never cached
        for monitor, status in wanted.items():
            rect = status.bar_rect
            assert rect is not None
            if monitor not in self._panels:
                panel, view = self._make_panel(rect, primary_height)
                self._panels[monitor] = (panel, view, rect)
            panel, view, old_rect = self._panels[monitor]
            if rect != old_rect:
                panel.setFrame_display_(self._appkit_rect(rect, primary_height), True)
                view.setFrameSize_((rect.w, rect.h))
                self._panels[monitor] = (panel, view, rect)
            if view.status != status:
                view.status = status
                view.setNeedsDisplay_(True)

    def close(self) -> None:
        for panel, _, _ in self._panels.values():
            panel.orderOut_(None)
        self._panels.clear()

    @staticmethod
    def _appkit_rect(rect: Rect, primary_height: int):
        f = flip_y(rect, primary_height)  # AX coordinates -> AppKit coordinates
        return NSMakeRect(f.x, f.y, f.w, f.h)

    def _make_panel(self, rect: Rect, primary_height: int):
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        frame = self._appkit_rect(rect, primary_height)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        panel.setLevel_(NSStatusWindowLevel)  # above normal windows, and above the menu bar
        panel.setIgnoresMouseEvents_(True)  # clicks fall through to whatever is underneath
        panel.setHasShadow_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        view = make_view(rect.w, rect.h, self._font_size, self._colors)
        panel.setContentView_(view)
        panel.orderFrontRegardless()
        return panel, view
