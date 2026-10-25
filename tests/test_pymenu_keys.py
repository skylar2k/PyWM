"""STEP 3 spec: pymenu.keys.dispatch(), the key table. Needs steps 1 and 2."""

import pytest

from pymenu.keys import KeyPress, Mod, dispatch
from pymenu.menu import Choice, Menu

C, A, S = Mod.CTRL, Mod.ALT, Mod.SHIFT


def press(key, mods=Mod.NONE, text=""):
    return KeyPress(key, mods, text)


def fresh(text="hello world", items=None, **kw) -> Menu:
    m = Menu(items or [f"i{k}" for k in range(8)], **kw)
    m.insert(text)
    return m


# --- typing ------------------------------------------------------------------------------


def test_typed_text_is_inserted():
    m = Menu(["a"])
    assert dispatch(m, press("a", text="a")) is None
    assert m.text == "a"


@pytest.mark.parametrize("text", ["", "\x01", "\x1b", "\r"])
def test_control_characters_and_empty_text_are_not_inserted(text):
    m = Menu(["a"])
    dispatch(m, press("a", text=text))
    assert m.text == ""


def test_unlisted_ctrl_and_alt_combinations_are_ignored():
    m = fresh()
    assert dispatch(m, press("z", C, "\x1a")) is None
    assert dispatch(m, press("q", A, "œ")) is None
    assert m.text == "hello world"


# --- Ctrl bindings -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "check"),
    [
        ("u", lambda m: (m.text, m.cursor) == ("", 0)),  # delete to start (cursor is at the end)
        ("w", lambda m: m.text == "hello "),
        ("h", lambda m: m.text == "hello worl"),  # backspace
        ("b", lambda m: m.cursor == 10),  # left
    ],
)
def test_ctrl_editing_keys(key, check):
    m = fresh()
    dispatch(m, press(key, C))
    assert check(m)


def test_ctrl_k_deletes_to_the_end_and_ctrl_d_deletes_forward():
    m = fresh()
    m.cursor = 5
    dispatch(m, press("d", C))
    assert m.text == "helloworld"
    dispatch(m, press("k", C))
    assert m.text == "hello"


def test_ctrl_a_e_f_move_the_cursor_or_the_list_like_home_end_right():
    m = fresh(text="ab", items=["x"])  # nothing matches "ab", so the keys act on the cursor
    dispatch(m, press("a", C))
    assert m.cursor == 0
    dispatch(m, press("f", C))
    assert m.cursor == 1
    dispatch(m, press("e", C))
    assert m.cursor == 2


def test_ctrl_n_and_p_move_the_selection():
    m = fresh(text="")
    dispatch(m, press("n", C))
    assert m.sel == 1
    dispatch(m, press("p", C))
    assert m.sel == 0


def test_ctrl_i_completes_like_tab():
    m = Menu(["apple", "apricot"])
    m.insert("ap")
    dispatch(m, press("i", C))
    assert m.text == "apple"


@pytest.mark.parametrize("key", ["c", "g", "leftbracket"])
def test_ctrl_c_g_and_bracket_cancel(key):
    m = fresh()
    dispatch(m, press(key, C))
    assert m.cancelled


@pytest.mark.parametrize("key", ["j", "m"])
def test_ctrl_j_and_m_are_return_and_still_close(key):
    m = Menu(["alpha"])
    assert dispatch(m, press(key, C)) == Choice("alpha", True)


def test_ctrl_left_and_right_move_by_words():
    m = fresh()
    dispatch(m, press("left", C))
    assert m.cursor == 6
    dispatch(m, press("left", C))
    assert m.cursor == 0
    dispatch(m, press("right", C))
    assert m.cursor == 5


def test_ctrl_y_pastes_the_first_line_of_the_clipboard():
    m = Menu(["a"])
    dispatch(m, press("y", C), paste=lambda: "pasted\nsecond line")
    assert m.text == "pasted"


# --- Alt bindings ------------------------------------------------------------------------


def test_alt_b_and_f_move_by_words():
    m = fresh()
    dispatch(m, press("b", A))
    assert m.cursor == 6
    dispatch(m, press("f", A))
    assert m.cursor == 11


def test_alt_h_j_k_l_navigate_the_list():
    m = fresh(text="", per_page=3)
    dispatch(m, press("l", A))
    assert m.sel == 1
    dispatch(m, press("h", A))
    assert m.sel == 0
    dispatch(m, press("j", A))
    assert (m.sel, m.page_start) == (3, 3)
    dispatch(m, press("k", A))
    assert (m.sel, m.page_start) == (0, 0)


def test_alt_g_is_home_and_alt_shift_g_is_end():
    m = fresh(text="", per_page=3)
    dispatch(m, press("g", A | S))
    assert m.sel == 7
    dispatch(m, press("g", A))
    assert m.sel == 0


# --- plain keys --------------------------------------------------------------------------


def test_plain_editing_and_navigation_keys():
    m = fresh(text="ab", items=["x"])
    dispatch(m, press("backspace"))
    assert m.text == "a"
    dispatch(m, press("left"))
    dispatch(m, press("delete"))
    assert m.text == ""
    m2 = fresh(text="", per_page=3)
    dispatch(m2, press("down"))
    dispatch(m2, press("down"))
    dispatch(m2, press("up"))
    assert m2.sel == 1
    dispatch(m2, press("pagedown"))
    assert m2.page_start == 3
    dispatch(m2, press("pageup"))
    assert m2.page_start == 0


def test_tab_completes_and_escape_cancels():
    m = Menu(["apple"])
    m.insert("ap")
    dispatch(m, press("tab"))
    assert m.text == "apple"
    dispatch(m, press("escape"))
    assert m.cancelled


def test_return_variants():
    assert dispatch(Menu(["alpha", "beta"]), press("return")) == Choice("alpha", True)
    m = Menu(["alpha", "beta"])
    m.insert("a")
    assert dispatch(m, press("return", S)) == Choice("a", True)
    assert dispatch(Menu(["alpha"]), press("return", C)) == Choice("alpha", False)
    m2 = Menu(["alpha"])
    m2.insert("a")
    assert dispatch(m2, press("return", C | S)) == Choice("a", False)
