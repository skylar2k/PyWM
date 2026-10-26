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


type Action = Callable[[Menu], None]

# The bindings are data: a key name maps to an *unbound* Menu method, called as `action(menu)`.
# Defined at module level, so a typo in a method name fails the moment this module is imported.
_PLAIN: dict[str, Action] = {
    "left": Menu.left,
    "right": Menu.right,
    "up": Menu.select_prev,
    "down": Menu.select_next,
    "home": Menu.home,
    "end": Menu.end,
    "pageup": Menu.page_prev,
    "pagedown": Menu.page_next,
    "delete": Menu.delete,
    "backspace": Menu.backspace,
    "tab": Menu.complete,
    "escape": Menu.cancel,
}

_CTRL: dict[str, Action] = {
    "a": Menu.home,
    "b": Menu.left,
    "c": Menu.cancel,
    "d": Menu.delete,
    "e": Menu.end,
    "f": Menu.right,
    "g": Menu.cancel,
    "h": Menu.backspace,
    "i": Menu.complete,
    "n": Menu.select_next,
    "p": Menu.select_prev,
    "k": Menu.delete_to_end,
    "u": Menu.delete_to_start,
    "w": Menu.delete_word_back,
    "left": Menu.word_left,
    "right": Menu.word_right,
    "leftbracket": Menu.cancel,
}

_ALT: dict[str, Action] = {
    "b": Menu.word_left,
    "f": Menu.word_right,
    "g": Menu.home,  # Alt+Shift+g is End; see dispatch()
    "h": Menu.select_prev,
    "j": Menu.page_next,
    "k": Menu.page_prev,
    "l": Menu.select_next,
}


def dispatch(menu: Menu, press: KeyPress, *, paste: Callable[[], str] = lambda: "") -> Choice | None:
    """Apply one key press to the menu. Returns a Choice when Return was pressed, otherwise None.

    `paste` returns the clipboard text; Ctrl+y inserts its first line.
    """
    key, shift = press.key, Mod.SHIFT in press.mods

    # Like dmenu, Ctrl takes precedence over Alt, and in either group a key that is not listed
    # is ignored (it must never be typed into the input).
    if Mod.CTRL in press.mods:
        if key in ("j", "m"):  # Ctrl+j / Ctrl+m are Return, and they still close the menu
            return menu.accept(shift=shift)
        if key == "return":  # Ctrl+Return accepts but keeps the menu open
            return menu.accept(shift=shift, ctrl=True)
        if key == "y":
            menu.insert(paste().partition("\n")[0])  # only the first line of the clipboard
        elif action := _CTRL.get(key):
            action(menu)
        return None

    if Mod.ALT in press.mods:
        if key == "g" and shift:  # Alt+Shift+g: End
            Menu.end(menu)
        elif action := _ALT.get(key):
            action(menu)
        return None

    if key == "return":
        return menu.accept(shift=shift)
    if action := _PLAIN.get(key):
        action(menu)
    elif press.text and press.text.isprintable():  # anything else that types a character
        menu.insert(press.text)
    return None
