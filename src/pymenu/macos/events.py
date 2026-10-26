"""Turning a macOS key event into the `KeyPress` that `keys.dispatch` understands.

This is the seam between the operating system and the pure part of pymenu. Everything on the far
side of it (`keys.py`, `menu.py`, `match.py`) has never heard of AppKit, which is why it is tested
without a window. This file is pure too: it takes plain integers and strings, so it is tested the
same way, and it imports nothing from AppKit.

What an `NSEvent` for a key press gives us:

    event.keyCode()           a number naming the *physical* key (the same on every keyboard layout)
    event.modifierFlags()     a bit mask: which of Shift / Control / Option / Command are held
    event.characters()        the text the press produces *with* the modifiers applied
                              ("A" for Shift+a, but an odd symbol for Option+a, which is why we
                              ignore the text whenever Control or Option is held)
"""

from pymenu.keys import KeyPress, Mod

# NSEvent.ModifierFlags. The four we care about; the event also carries Caps Lock, "this is an
# arrow key", "this came from the numeric keypad" and more, which we simply mask away.
SHIFT, CONTROL, OPTION, COMMAND = 1 << 17, 1 << 18, 1 << 19, 1 << 20

# Carbon's kVK_* virtual key codes, for the keys dmenu has bindings for. They name key *positions*,
# so "j" means "the key where QWERTY has j" on every layout; that is what shortcuts want.
KEYCODES: dict[int, str] = {
    0: "a", 11: "b", 8: "c", 2: "d", 14: "e", 3: "f", 5: "g", 4: "h", 34: "i", 38: "j", 40: "k",
    37: "l", 46: "m", 45: "n", 31: "o", 35: "p", 12: "q", 15: "r", 1: "s", 17: "t", 32: "u", 9: "v",
    13: "w", 7: "x", 16: "y", 6: "z",
    33: "leftbracket",
    36: "return", 76: "return",  # the main Return key and the keypad Enter
    48: "tab", 53: "escape",
    51: "backspace",  # macOS calls this key "delete"
    117: "delete",  # ... and this one "forward delete"
    115: "home", 119: "end", 116: "pageup", 121: "pagedown",
    123: "left", 124: "right", 125: "down", 126: "up",
}  # fmt: skip

KEY_V = 9


def to_keypress(keycode: int, flags: int, characters: str) -> KeyPress | None:
    """The KeyPress for one macOS key event, or None if pymenu has no use for it."""
    mods = Mod.NONE
    if flags & SHIFT:
        mods |= Mod.SHIFT
    if flags & CONTROL:
        mods |= Mod.CTRL
    if flags & OPTION:
        mods |= Mod.ALT

    if flags & COMMAND:
        # A Mac habit dmenu (an X11 program) does not have: Cmd+V pastes. Reuse Ctrl+y, which pastes.
        # Every other Cmd shortcut is not ours to handle.
        return KeyPress("y", Mod.CTRL) if keycode == KEY_V else None

    # With Control or Option held, the characters are not what the user "typed", so never insert them.
    text = "" if mods & (Mod.CTRL | Mod.ALT) else characters
    return KeyPress(KEYCODES.get(keycode, ""), mods, text)
