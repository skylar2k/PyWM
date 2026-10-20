"""Global hotkeys with a `CGEventTap`.

An event tap sits in the stream of keyboard events *before* apps see them. Our
callback looks at every key press; if it matches a binding we return `None`, which
swallows the event (so Option+J never types a ∆ into your editor), otherwise we
hand the event back untouched.

Rules of the road:

* The callback runs inside the system's event delivery, so it must be fast.
  We only look the key up in a dict and queue the real work on the run loop.
* macOS disables a tap that is too slow, or when secure input is active. We
  watch for the "tap disabled" pseudo-events and switch it back on.
* A tap needs Accessibility to swallow events and Input Monitoring to see them.
"""

import logging
from collections.abc import Callable

from CoreFoundation import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    kCFRunLoopCommonModes,
)
from PyObjCTools import AppHelper
from Quartz import (
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventTapCreate,
    CGEventTapEnable,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput,
    kCGEventTapOptionDefault,
    kCGHeadInsertEventTap,
    kCGKeyboardEventKeycode,
    kCGSessionEventTap,
)

from pywm.core.keys import Chord
from pywm.platform.macos.keycodes import KEYCODES, RELEVANT_FLAGS, flags_for

log = logging.getLogger(__name__)


class HotkeyTap:
    def __init__(self, chords: set[Chord], on_chord: Callable[[Chord], None]) -> None:
        self._table: dict[tuple[int, int], Chord] = {}
        for chord in chords:
            mods, key = chord
            self._table[(flags_for(mods), KEYCODES[key])] = chord
        self._on_chord = on_chord
        self._swallowed: set[int] = set()  # key codes whose key-up we must also swallow
        self._tap = None
        self._source = None

    def start(self) -> bool:
        """Install the tap. Returns False (and logs why) if macOS refuses."""
        mask = (1 << kCGEventKeyDown) | (1 << kCGEventKeyUp)

        def callback(proxy, event_type, event, refcon):
            return self._handle(event_type, event)

        self._callback = callback  # keep the C trampoline alive for as long as the tap exists
        self._tap = CGEventTapCreate(
            kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionDefault, mask, callback, None
        )
        if self._tap is None:
            log.error("could not create the keyboard event tap: grant Accessibility and Input Monitoring")
            return False
        self._source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), self._source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, True)
        return True

    def _handle(self, event_type, event):
        if event_type in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput):
            log.warning("event tap was disabled by macOS; re-enabling")
            CGEventTapEnable(self._tap, True)
            return event
        code = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        if event_type == kCGEventKeyUp:
            if code in self._swallowed:
                self._swallowed.discard(code)
                return None  # its key-down was ours, so the matching key-up is too
            return event
        chord = self._table.get((CGEventGetFlags(event) & RELEVANT_FLAGS, code))
        if chord is None:
            return event
        self._swallowed.add(code)
        AppHelper.callAfter(self._on_chord, chord)  # do the real work outside the tap callback
        return None
