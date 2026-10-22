"""Physical key positions (Carbon `kVK_ANSI_*` virtual key codes) and modifier masks.

These identify *where a key is on the keyboard*, not what it types. That is
what a window manager wants ("the key left of k"), and it sidesteps Option
turning letters into symbols. The cost: a key's position is the same on every
layout, so on a layout that moves punctuation, "comma" is the key where a US
keyboard has its comma. The letters, digits, return, space and tab used by the
default bindings sit in the same place on US and Nordic layouts.
"""

from functools import cache

from Quartz import (
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
)

from pywm.core.keys import KEY_NAMES, Mod

KEYCODES: dict[str, int] = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05, "z": 0x06, "x": 0x07,
    "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10,
    "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "equal": 0x18,
    "9": 0x19, "7": 0x1A, "minus": 0x1B, "8": 0x1C, "0": 0x1D, "rightbracket": 0x1E, "o": 0x1F,
    "u": 0x20, "leftbracket": 0x21, "i": 0x22, "p": 0x23, "return": 0x24, "l": 0x25, "j": 0x26,
    "quote": 0x27, "k": 0x28, "semicolon": 0x29, "backslash": 0x2A, "comma": 0x2B, "slash": 0x2C,
    "n": 0x2D, "m": 0x2E, "period": 0x2F, "tab": 0x30, "space": 0x31, "grave": 0x32,
    "delete": 0x33, "escape": 0x35, "left": 0x7B, "right": 0x7C, "down": 0x7D, "up": 0x7E,
}  # fmt: skip

# Keep the config-side key names and the hardware table in sync.
missing = KEY_NAMES - KEYCODES.keys()
assert not missing, f"no keycode for: {sorted(missing)}"

# IOKit's device-dependent bits (IOLLEvent.h): which Option key is down.
NX_DEVICELALTKEYMASK = 0x00000020
NX_DEVICERALTKEYMASK = 0x00000040

ALT_FLAG = kCGEventFlagMaskAlternate

FLAG_FOR: dict[Mod, int] = {
    Mod.SHIFT: kCGEventFlagMaskShift,
    Mod.CTRL: kCGEventFlagMaskControl,
    Mod.CMD: kCGEventFlagMaskCommand,
}

SIDE_FLAGS: dict[Mod, int] = {Mod.L_ALT: NX_DEVICELALTKEYMASK, Mod.R_ALT: NX_DEVICERALTKEYMASK}


@cache
def candidates(flags: int) -> tuple[Mod, ...]:
    """The `Mod` values an event with these flags can satisfy, most specific first."""
    base = Mod.NONE
    for mod, flag in FLAG_FOR.items():
        if flags & flag:
            base |= mod

    if not flags & ALT_FLAG:
        return (base,)

    sides = Mod.NONE
    for mod, flag in SIDE_FLAGS.items():
        if flags & flag:
            sides |= mod

    # Left Option held -> try a LALT chord first, then fall back to generic ALT
    # No device bits (synethetic event) -> only generic ALT can match.
    return (base | sides, base | Mod.ALT) if sides else (base | Mod.Alt,)
