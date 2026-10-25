"""STEP 3: from a key press to a Menu method: the big `switch` in dmenu's `keypress()`, as data.

`KeyPress` is what the window layer will build from an NSEvent (step 5); `dispatch` is pure, so it is
tested without a keyboard. Keys are named by *physical key*: letters "a".."z", and "left", "right",
"up", "down", "home", "end", "pageup", "pagedown", "delete" (forward), "backspace", "return",
"escape", "tab", "leftbracket".

dmenu's bindings (all that is not listed is ignored when Ctrl or Alt is held):

    plain      Left/Right/Up/Down/Home/End/PageUp/PageDown/Delete/Backspace/Tab -> the Menu method
               Return -> accept (Shift: print the typed text instead)   Escape -> cancel
               anything else with typed text -> insert it (but never control characters)
    Ctrl       a Home   b Left   c Escape   d Delete   e End   f Right   g Escape   h Backspace
               i Tab    n Down   p Up       j or m: Return, and it closes even though Ctrl is held
               k delete to end     u delete to start    w delete word back    y paste (first line)
               Left/Right word movement     Return accepts but keeps the menu open
               leftbracket ("Ctrl+[") cancels
    Alt        b word left   f word right   g Home   Shift+g End
               h Up   j PageDown   k PageUp   l Down
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntFlag

from pymenu.menu import Choice, Menu


class Mod(IntFlag):
    NONE = 0
    SHIFT = 1
    CTRL = 2
    ALT = 4  # Option


@dataclass(frozen=True)
class KeyPress:
    key: str  # physical key name, see the module docstring
    mods: Mod = Mod.NONE
    text: str = ""  # the characters this press types, if any ("" for arrows and the like)


def dispatch(menu: Menu, press: KeyPress, *, paste: Callable[[], str] = lambda: "") -> Choice | None:
    """Apply one key press to the menu. Returns a Choice when Return was pressed, otherwise None.

    `paste` returns the clipboard text; Ctrl+y inserts its first line.
    """
    raise NotImplementedError("step 3: implement dispatch(); see the table in the module docstring")
