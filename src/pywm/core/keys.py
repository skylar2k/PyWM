"""Key bindings, written the way dwm's `keys[]` table is: modifiers, key, function, argument."""

from collections.abc import Callable
from enum import IntFlag
from typing import Any


class Mod(IntFlag):
    """Modifier keys. Combine them with `|`, e.g. `Mod.ALT | Mod.SHIFT`."""

    NONE = 0
    SHIFT = 1
    CTRL = 2
    ALT = 4  # either Option key
    CMD = 8
    L_ALT = 16
    R_ALT = 32


type Chord = tuple[Mod, str]

# Names of *physical* keys. The macOS adapter maps these to hardware key codes.
KEY_NAMES = frozenset([
    *"abcdefghijklmnopqrstuvwxyz0123456789",
    "return", "space", "tab", "escape", "delete",
    "left", "right", "up", "down",
    "comma", "period", "slash", "semicolon", "quote", "minus", "equal",
    "backslash", "grave", "leftbracket", "rightbracket",
])  # fmt: skip


class Key:
    """One binding: `Key(Mod.ALT, "j", WM.focus_stack, +1)` calls `WM.focus_stack(wm, +1)`.

    `action` is just a function whose first parameter is the window manager, and `args` are the
    rest. Passing the function itself (rather than its name) means a typo is an immediate
    NameError when the config loads, and "go to definition" works in your editor.
    """

    __slots__ = ("action", "args", "key", "mods")

    def __init__(self, mods: Mod, key: str, action: Callable[..., None], *args: Any) -> None:
        if key not in KEY_NAMES:
            raise ValueError(f"unknown key {key!r}; known keys: {sorted(KEY_NAMES)}")
        self.mods, self.key, self.action, self.args = mods, key, action, args

    @property
    def chord(self) -> Chord:
        return (self.mods, self.key)

    def __repr__(self) -> str:
        return f"Key({self.mods!r}, {self.key!r}, {self.action.__qualname__}, *{self.args!r})"
