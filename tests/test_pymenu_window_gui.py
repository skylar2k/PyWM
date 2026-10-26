"""End to end: the real window, the real event loop, synthetic key events.

Opt-in, because each case puts a window on your screen and takes keyboard focus for a moment:

    PYMENU_GUI_TESTS=1 uv run pytest tests/test_pymenu_window_gui.py -q

Each case runs pymenu in a child process (AppKit wants the main thread of a process of its own),
schedules key events with timers before the loop starts, and checks what the program printed and
which exit status it returned: exactly what a shell script would see.

The events are delivered with `window.sendEvent_`, the same path real key presses take inside the
app. That needs no macOS permission, but it does mean these tests prove the program's *logic*;
`test_the_window_really_gets_the_keyboard` is the one that checks real activation.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = [
    pytest.mark.skipif(sys.platform != "darwin", reason="AppKit"),
    pytest.mark.skipif(
        not os.environ.get("PYMENU_GUI_TESTS"), reason="opens a window; set PYMENU_GUI_TESTS=1"
    ),
]

# macOS virtual key codes (see macos/events.py) and the Control modifier flag.
RETURN, ESCAPE, DOWN, KEY_B, KEY_E, KEY_Z = 36, 53, 125, 11, 14, 6
CTRL = 1 << 18

DRIVER = textwrap.dedent(
    """
    import json, sys
    from AppKit import NSApp, NSEvent
    from PyObjCTools import AppHelper
    from pymenu.cli import main

    steps, argv = json.loads(sys.argv[1]), json.loads(sys.argv[2])

    def send(keycode, flags, chars):
        window = NSApp().windows()[0]
        event = NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
            10, (0, 0), flags, 0, window.windowNumber(), None, chars, chars, False, keycode)  # 10 = key down
        window.sendEvent_(event)

    def report():
        window = NSApp().windows()[0]
        f, s = window.frame(), window.screen().frame()
        print("key window:", bool(window.isKeyWindow()), "| app active:", bool(NSApp().isActive()),
              "| frame:", f.origin.x, f.origin.y, f.size.width, f.size.height,
              "| screen:", s.origin.x, s.origin.y, s.size.width, s.size.height, file=sys.stderr)

    AppHelper.callLater(0.7, report)
    delay = 0.9
    for keycode, flags, chars in steps:
        AppHelper.callLater(delay, send, keycode, flags, chars)
        delay += 0.15
    sys.exit(main(argv))  # reads the items from stdin, exactly like the `pymenu` command
    """  # noqa: E501 (the NSEvent factory method has a very long name)
)


def run(steps, items=("alpha", "beta", "gamma"), argv=()):
    result = subprocess.run(
        [sys.executable, "-c", DRIVER, json.dumps(steps), json.dumps(list(argv))],
        input="".join(item + "\n" for item in items),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout, result.returncode, result.stderr


def test_choosing_the_selected_item_prints_it_and_exits_0():
    out, code, _ = run([[RETURN, 0, "\r"]])
    assert (out, code) == ("alpha\n", 0)


def test_typing_narrows_the_list_then_return_chooses_the_match():
    out, code, _ = run([[KEY_B, 0, "b"], [KEY_E, 0, "e"], [RETURN, 0, "\r"]])
    assert (out, code) == ("beta\n", 0)


def test_arrow_keys_move_the_selection():
    out, code, _ = run([[DOWN, 0, ""], [DOWN, 0, ""], [RETURN, 0, "\r"]])
    assert (out, code) == ("gamma\n", 0)


def test_escape_cancels_with_exit_status_1_and_prints_nothing():
    out, code, _ = run([[ESCAPE, 0, "\x1b"]])
    assert (out, code) == ("", 1)


def test_text_that_matches_nothing_is_printed_as_typed():
    out, code, _ = run([[KEY_Z, 0, "z"], [KEY_Z, 0, "z"], [RETURN, 0, "\r"]])
    assert (out, code) == ("zz\n", 0)


def test_ctrl_return_prints_without_closing_and_escape_then_ends_it():
    out, code, _ = run([[RETURN, CTRL, "\r"], [DOWN, 0, ""], [RETURN, CTRL, "\r"], [ESCAPE, 0, "\x1b"]])
    assert (out, code) == ("alpha\nbeta\n", 1)


def test_the_window_really_gets_the_keyboard():
    _, _, err = run([[ESCAPE, 0, "\x1b"]])
    assert "key window: True" in err, err


def test_the_command_line_flags_work_end_to_end():
    # -l: a vertical list; -p: a prompt; both only change what is drawn, so the choice is the same
    out, code, _ = run([[DOWN, 0, ""], [RETURN, 0, "\r"]], argv=["-l", "2", "-p", "pick:"])
    assert (out, code) == ("beta\n", 0)


def test_dash_i_matches_case_insensitively():
    out, code, _ = run([[0, 0, "a"], [RETURN, 0, "\r"]], items=("Zebra", "Alpha", "beta"), argv=["-i"])
    assert (out, code) == ("Alpha\n", 0)


def test_no_items_on_stdin_makes_a_plain_text_prompt():
    out, code, _ = run([[KEY_Z, 0, "z"], [RETURN, 0, "\r"]], items=(), argv=["-p", "name:"])
    assert (out, code) == ("z\n", 0)


def _geometry(stderr):
    """(window, screen) rectangles from the driver's report line."""
    numbers = lambda part: [float(n) for n in part.split()[:4]]  # noqa: E731
    frame, screen = stderr.split("| frame:")[1].split("| screen:")
    return numbers(frame), numbers(screen)


def test_dash_c_puts_the_real_window_in_the_middle_of_its_screen():
    out, code, err = run([[DOWN, 0, ""], [RETURN, 0, "\r"]], argv=["-c", "-W", "600"])
    assert (out, code) == ("beta\n", 0)  # a centred menu still works as a menu
    (x, y, w, h), (sx, sy, sw, sh) = _geometry(err)
    assert w == 600
    assert abs((x + w / 2) - (sx + sw / 2)) <= 1  # centred horizontally
    assert abs((y + h / 2) - (sy + sh / 2)) <= 1  # ... and vertically


def test_without_dash_c_the_window_spans_the_top_of_the_screen():
    _, _, err = run([[ESCAPE, 0, "\x1b"]])
    (x, y, w, h), (sx, sy, sw, sh) = _geometry(err)
    assert (x, w) == (sx, sw) and abs((y + h) - (sy + sh)) <= 1
