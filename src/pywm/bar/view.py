"""Drawing the bar: tag boxes, layout symbol and the focused window's title, dwm-style."""

from AppKit import (
    NSBitmapImageFileTypePNG,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSRectFill,
    NSString,
    NSView,
)
from Foundation import NSMakeRect

from pywm.core.wm import MonitorStatus

PADDING = 10


def _color(rgb: int):
    return NSColor.colorWithSRGBRed_green_blue_alpha_(
        (rgb >> 16 & 0xFF) / 255, (rgb >> 8 & 0xFF) / 255, (rgb & 0xFF) / 255, 1.0
    )


def draw_cell(font, height, text, x, fg, bg=None, width=None, left=False) -> float:
    """Draw `text` in a padded cell starting at x. Returns the cell's right edge.

    A module-level function on purpose: inside an NSObject subclass PyObjC would read
    underscores in a method name as Objective-C argument separators.
    """
    attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: _color(fg)}
    string = NSString.stringWithString_(text)
    size = string.sizeWithAttributes_(attrs)
    cell_w = width if width is not None else size.width + 2 * PADDING
    if bg is not None:
        _color(bg).setFill()
        NSRectFill(NSMakeRect(x, 0, cell_w, height))
    text_x = x + PADDING if left else x + (cell_w - size.width) / 2
    string.drawAtPoint_withAttributes_((text_x, (height - size.height) / 2), attrs)
    return x + cell_w


class BarView(NSView):
    """An NSView that paints a `MonitorStatus`. Set `.status` then call `setNeedsDisplay_`."""

    def isFlipped(self):  # top-left origin, like everything else in pywm
        return True

    def drawRect_(self, dirty):
        b = self.bounds()
        h, font, colors = b.size.height, self.font, self.colors
        _color(colors["norm_bg"]).setFill()
        NSRectFill(b)
        s: MonitorStatus | None = self.status
        if s is None:
            return
        x = 0.0
        for i, name in enumerate(s.tag_names):
            bit = 1 << i
            selected = bool(s.selected & bit)
            fg = colors["sel_fg" if selected else "norm_fg"]
            x_end = draw_cell(font, h, name, x, fg, colors["sel_bg"] if selected else None)
            if s.occupied & bit:  # dwm marks tags that have windows with a small square
                _color(fg).setFill()
                NSRectFill(NSMakeRect(x + 3, 3, 4, 4))
            x = x_end
        x = draw_cell(font, h, s.layout_symbol, x, colors["norm_fg"])
        prefix = "sel" if s.current else "norm"  # the focused monitor's title is highlighted
        draw_cell(
            font, h, s.title, x, colors[f"{prefix}_fg"], colors[f"{prefix}_bg"], b.size.width - x, left=True
        )


def make_view(width: float, height: float, font_size: int, colors: dict[str, int]) -> BarView:
    view = BarView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    view.status = None
    view.font = NSFont.systemFontOfSize_(font_size)
    view.colors = colors
    return view


def snapshot_png(view: BarView) -> bytes:
    """Render a view offscreen to PNG bytes (no screen or permissions needed)."""
    rep = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
    view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), rep)
    return bytes(rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {}))
