"""STEP 4: drawing the menu: dmenu's `drawmenu()` plus the parts of drw.c it needs.

What to draw, left to right (horizontal) or top to bottom (vertical, `lines > 0`):
the prompt (selected colours) | the input text with a cursor | "<" if there is a previous page |
the visible items (the selected one in the selected colours, marked ones in the "out" colours) |
">" if there is a next page.

Everything it needs is on the `Menu` (text, cursor, page(), sel, page_start, marked) and in
`Settings` (colours, font, prompt). Look at `src/pywm/bar/view.py` in the pywm project for a small
working example of text cells drawn with AppKit.

Hints: an NSView subclass overrides `drawRect_`; `isFlipped` returning True gives a top-left origin;
`NSString.drawAtPoint_withAttributes_` draws text; `NSRectFill` fills rectangles.
"""

from AppKit import NSView


class MenuView(NSView):
    def isFlipped(self):
        return True

    def drawRect_(self, dirty):
        raise NotImplementedError("step 4: draw the prompt, the input and cursor, and the items")
