"""macos/events.py: from a macOS key event to a KeyPress. Pure, so it needs no window."""

from pymenu.keys import KeyPress, Mod
from pymenu.macos.events import COMMAND, CONTROL, KEYCODES, OPTION, SHIFT, to_keypress

KEY_J, KEY_V, KEY_C, DOWN, RETURN, BACKSPACE, FORWARD_DELETE, DIGIT_1 = 38, 9, 8, 125, 36, 51, 117, 18
CAPS_LOCK, ARROW_FLAG = 1 << 16, 1 << 23  # modifier bits an arrow key or Caps Lock adds; we must not care


def test_a_plain_letter_keeps_its_key_name_and_its_text():
    assert to_keypress(KEY_J, 0, "j") == KeyPress("j", Mod.NONE, "j")


def test_shift_is_a_modifier_and_the_shifted_text_is_kept():
    assert to_keypress(KEY_J, SHIFT, "J") == KeyPress("j", Mod.SHIFT, "J")


def test_control_and_option_never_produce_text():
    assert to_keypress(KEY_J, CONTROL, "\n") == KeyPress("j", Mod.CTRL, "")
    assert to_keypress(KEY_J, OPTION, "∆") == KeyPress("j", Mod.ALT, "")  # Option+j types a symbol on a Mac


def test_modifiers_combine():
    assert to_keypress(RETURN, CONTROL | SHIFT, "\r") == KeyPress("return", Mod.CTRL | Mod.SHIFT, "")


def test_special_keys_are_named_by_position():
    assert to_keypress(DOWN, ARROW_FLAG, "").key == "down"
    assert to_keypress(RETURN, 0, "\r").key == "return"
    assert to_keypress(76, 0, "\x03").key == "return"  # the keypad Enter key


def test_macos_delete_is_backspace_and_forward_delete_is_delete():
    assert to_keypress(BACKSPACE, 0, "\x7f").key == "backspace"
    assert to_keypress(FORWARD_DELETE, 0, "").key == "delete"


def test_caps_lock_and_arrow_flags_do_not_count_as_modifiers():
    assert to_keypress(KEY_J, CAPS_LOCK | ARROW_FLAG, "J").mods == Mod.NONE


def test_a_key_without_a_name_still_types_its_character():
    assert to_keypress(DIGIT_1, 0, "1") == KeyPress("", Mod.NONE, "1")


def test_cmd_v_pastes_by_becoming_ctrl_y():
    assert to_keypress(KEY_V, COMMAND, "v") == KeyPress("y", Mod.CTRL)


def test_other_cmd_shortcuts_are_not_ours():
    assert to_keypress(KEY_C, COMMAND, "c") is None


def test_every_named_key_is_a_key_name_that_keys_py_documents():
    documented = set("abcdefghijklmnopqrstuvwxyz") | {
        "left", "right", "up", "down", "home", "end", "pageup", "pagedown", "delete", "backspace",
        "return", "escape", "tab", "leftbracket",
    }  # fmt: skip
    assert set(KEYCODES.values()) <= documented
