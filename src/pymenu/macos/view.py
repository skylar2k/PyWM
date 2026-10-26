"""STEP 4: drawing the menu. A port of dmenu's `drawmenu()`, plus the bits of drw.c it leans on.

The picture, left to right (a horizontal menu) or top to bottom (vertical, `lines > 0`):

    horizontal:   | prompt | input text with cursor |  <  item  item  item  item  > |
    vertical:     | prompt | input text with cursor |
                           | item                                                  |
                           | item (selected: a different background)               |

How AppKit drawing works, which is all you need to read this file:

* An `NSView` draws itself in `drawRect_`, and AppKit calls it whenever the view needs repainting
  (`view.setNeedsDisplay_(True)` asks for that). Inside it, you "fill a rectangle" and "draw a string"
  with the *current graphics context*; there is no canvas object to pass around.
* By default AppKit's y axis points UP. Returning True from `isFlipped` makes y point down inside
  this view, which is how screens and dmenu think about it.
* `NSRectClip` restricts all further drawing to a rectangle, so a long item cannot spill into its
  neighbour. `saveGraphicsState` / `restoreGraphicsState` bracket it so the clip does not leak.

Everything the drawing needs lives in two objects: the `Menu` (text, cursor, page, selection,
marked items) and the `Style` below (font and colours). The view never changes the menu.
"""

import math
from dataclasses import dataclass
from typing import Any

from AppKit import (
    NSBitmapImageRep,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSFontWeightRegular,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSRectClip,
    NSRectFill,
    NSString,
    NSView,
)
from Foundation import NSMakeRect

from pymenu.config import Settings
from pymenu.menu import Menu


def parse_font(spec: str) -> Any:
    """'Menlo:size=13' -> an NSFont. 'monospace' means the system's fixed-width font."""
    name, _, options = spec.partition(":")
    size = 13.0
    for option in options.split(":"):
        if option.startswith("size="):
            size = float(option.removeprefix("size="))
    if name.strip().lower() in ("", "monospace", "mono"):
        return NSFont.monospacedSystemFontOfSize_weight_(size, NSFontWeightRegular)
    return NSFont.fontWithName_size_(name, size) or NSFont.systemFontOfSize_(size)


@dataclass
class Style:
    """What dmenu keeps in `drw`: the font and the colour schemes, plus the sizes derived from them."""

    font: Any
    colors: dict[str, int]  # 0xRRGGBB, keys as in config.py
    line_height: int  # height of one line of text (dmenu: drw->fonts->h)

    @property
    def bh(self) -> int:
        """The height of one row of the menu: a line of text plus a pixel above and below."""
        return self.line_height + 2

    @property
    def padding(self) -> int:
        """Left plus right padding of a cell (dmenu's `lrpad`); half of it goes on each side."""
        return self.line_height

    def scheme(self, name: str) -> tuple[int, int]:
        """(foreground, background) for 'norm', 'sel' or 'out': dmenu's three colour schemes."""
        return self.colors[f"{name}_fg"], self.colors[f"{name}_bg"]


def make_style(settings: Settings) -> Style:
    font = parse_font(settings.font)
    return Style(font, settings.colors, math.ceil(font.ascender() - font.descender()))


def _color(rgb: int) -> Any:
    return NSColor.colorWithSRGBRed_green_blue_alpha_(
        (rgb >> 16 & 0xFF) / 255, (rgb >> 8 & 0xFF) / 255, (rgb & 0xFF) / 255, 1.0
    )


def text_width(style: Style, text: str) -> float:
    return NSString.stringWithString_(text).sizeWithAttributes_({NSFontAttributeName: style.font}).width


def cell_width(style: Style, text: str) -> float:
    """dmenu's TEXTW(): the text plus the cell's padding."""
    return text_width(style, text) + style.padding


def draw_text(style: Style, x: float, y: float, w: float, text: str, scheme: tuple[int, int]) -> float:
    """dmenu's `drw_text`: fill a w x bh cell with the scheme's background, draw `text` in it,
    and return the x where the next cell starts. Text that does not fit is clipped."""
    if w <= 0:
        return x
    foreground, background = scheme
    cell = NSMakeRect(x, y, w, style.bh)
    _color(background).setFill()
    NSRectFill(cell)

    NSGraphicsContext.saveGraphicsState()
    NSRectClip(cell)  # everything drawn until the restore below stays inside the cell
    attributes = {NSFontAttributeName: style.font, NSForegroundColorAttributeName: _color(foreground)}
    where = (x + style.padding / 2, y + (style.bh - style.line_height) / 2)
    NSString.stringWithString_(text).drawAtPoint_withAttributes_(where, attributes)
    NSGraphicsContext.restoreGraphicsState()
    return x + w


def paint_menu(width: float, menu: Menu, settings: Settings, style: Style) -> None:
    """Draw the whole menu into the current graphics context (dmenu's `drawmenu()`)."""
    norm, sel, out = style.scheme("norm"), style.scheme("sel"), style.scheme("out")

    # 1. Clear everything to the normal background.
    _color(norm[1]).setFill()
    NSRectFill(NSMakeRect(0, 0, width, (menu.lines + 1) * style.bh))

    # 2. The prompt, in the "selected" colours, if there is one.
    x = 0.0
    if settings.prompt:
        prompt_width = cell_width(style, settings.prompt) - style.padding / 4
        x = draw_text(style, x, 0, prompt_width, settings.prompt, sel)

    # 3. The input field. In a vertical menu (or when nothing matches) it takes the rest of the row;
    #    in a horizontal one it takes a third of the width and the items go to its right.
    vertical = menu.lines > 0
    input_width = width / 3
    field_width = width - x if (vertical or not menu.matches) else input_width
    draw_text(style, x, 0, field_width, menu.text, norm)

    # 4. The cursor: a thin bar after the first `cursor` characters, if it is inside the field.
    cursor_x = text_width(style, menu.text[: menu.cursor]) + style.padding / 2 - 1
    if cursor_x < field_width:
        _color(norm[0]).setFill()
        NSRectFill(NSMakeRect(x + cursor_x, 2, 2, style.bh - 4))

    # 5. The items on the current page.
    page = list(enumerate(menu.page(), menu.page_start))  # [(index into matches, text), ...]

    def scheme_for(index: int, item: str) -> tuple[int, int]:
        if index == menu.sel:
            return sel
        return out if item in menu.marked else norm

    if vertical:
        # One item per row, starting one row below the input, lined up with the input field.
        for row, (index, item) in enumerate(page, start=1):
            draw_text(style, x, row * style.bh, width - x, item, scheme_for(index, item))
    elif menu.matches:
        # Items side by side after the input, with "<" and ">" showing that there are more pages.
        x += input_width
        arrow = cell_width(style, "<")
        if menu.page_start > 0:
            draw_text(style, x, 0, arrow, "<", norm)
        x += arrow
        for index, item in page:
            room = width - x - cell_width(style, ">")  # keep space for the ">"
            x = draw_text(style, x, 0, min(cell_width(style, item), room), item, scheme_for(index, item))
        if menu.page_start + menu.per_page < len(menu.matches):
            draw_text(style, width - cell_width(style, ">"), 0, cell_width(style, ">"), ">", norm)


class MenuView(NSView):
    """The view that paints a menu. Set `.menu`, `.settings` and `.style`, then ask it to redraw."""

    def isFlipped(self):  # y grows downwards, like on a screen
        return True

    def drawRect_(self, dirty):
        paint_menu(self.bounds().size.width, self.menu, self.settings, self.style)


def make_view(
    width: float, menu: Menu, settings: Settings, style: Style, view_class: type[MenuView] = MenuView
) -> MenuView:
    """Build a view. `view_class` lets the window pass a subclass that also receives keys."""
    height = (menu.lines + 1) * style.bh
    view = view_class.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    view.menu, view.settings, view.style = menu, settings, style
    return view


def render(view: MenuView) -> Any:
    """Draw a view into an in-memory bitmap (no screen needed); used by the tests, and handy for
    looking at the result with `rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})`."""
    rep: NSBitmapImageRep = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
    view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), rep)
    return rep
