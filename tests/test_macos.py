import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="needs PyObjC")


def test_every_key_name_has_a_hardware_key_code():
    from pywm.core.keys import KEY_NAMES
    from pywm.platform.macos.keycodes import KEYCODES

    assert KEYCODES.keys() >= KEY_NAMES


def test_modifier_flags_map_to_event_flag_bits():
    from Quartz import kCGEventFlagMaskAlternate, kCGEventFlagMaskShift

    from pywm.core.keys import Mod
    from pywm.platform.macos.keycodes import flags_for

    assert flags_for(Mod.ALT | Mod.SHIFT) == kCGEventFlagMaskAlternate | kCGEventFlagMaskShift
    assert flags_for(Mod.NONE) == 0


def test_hotkey_table_matches_chords_exactly_and_ignores_caps_lock():
    import Quartz

    import pywm.platform.macos.hotkeys as hk
    from pywm.core.keys import Mod
    from pywm.platform.macos.keycodes import KEYCODES, flags_for

    hits = []
    tap = hk.HotkeyTap({(Mod.ALT, "j")}, hits.append)
    hk.CGEventGetIntegerValueField = lambda event, field: event[0]
    hk.CGEventGetFlags = lambda event: event[1]
    hk.AppHelper.callAfter = lambda fn, *a: fn(*a)
    down, up = Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp
    alt = flags_for(Mod.ALT)
    j = KEYCODES["j"]

    assert tap._handle(down, (j, alt | Quartz.kCGEventFlagMaskAlphaShift)) is None  # swallowed
    assert hits == [(Mod.ALT, "j")]
    assert tap._handle(up, (j, 0)) is None  # its key-up is swallowed too
    event = (j, 0)
    assert tap._handle(down, event) is event  # plain j passes through
    event = (j, alt | flags_for(Mod.SHIFT))
    assert tap._handle(down, event) is event  # Option+Shift+j is a different chord
