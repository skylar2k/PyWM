"""STEP 2 spec: pymenu.menu.Menu. Needs step 1 (match) first."""

import pytest

from pymenu.menu import Choice, Menu


def numbered(n=8, **kw) -> Menu:
    return Menu([f"i{k}" for k in range(n)], **kw)


# --- construction (provided) ------------------------------------------------------------


def test_a_new_menu_selects_the_first_match_and_shows_the_first_page():
    m = numbered(8, per_page=3)
    assert (m.sel, m.page_start, m.page()) == (0, 0, ["i0", "i1", "i2"])


def test_page_size_defaults_to_lines_or_ten():
    assert numbered(3).per_page == 10
    assert numbered(3, lines=4).per_page == 4


def test_a_menu_with_no_items_has_no_selection():
    assert Menu([]).sel is None


# --- 2a: editing the text ---------------------------------------------------------------


def test_insert_puts_text_at_the_cursor_and_moves_it_after():
    m = Menu(["apple", "banana"])
    m.insert("ac")
    m.cursor = 1
    m.insert("b")
    assert (m.text, m.cursor) == ("abc", 2)


def test_insert_narrows_the_matches_and_resets_the_selection():
    m = Menu(["apple", "banana", "blueberry"])
    m.select_next()
    m.insert("b")
    assert m.matches == ["banana", "blueberry"]
    assert (m.sel, m.page_start) == (0, 0)


def test_backspace_deletes_before_the_cursor_and_rematches():
    m = Menu(["apple", "apply", "banana"])
    m.insert("appl")
    m.backspace()
    assert (m.text, m.cursor) == ("app", 3)
    assert m.matches == ["apple", "apply"]


def test_backspace_at_the_start_does_nothing():
    m = Menu(["a"])
    m.insert("x")
    m.cursor = 0
    m.backspace()
    assert (m.text, m.cursor) == ("x", 0)


def test_delete_word_back_keeps_what_is_right_of_the_cursor():
    m = Menu(["a"])
    m.insert("foo bar baz")
    m.cursor = 7
    m.delete_word_back()
    assert (m.text, m.cursor) == ("foo  baz", 4)


def test_delete_word_back_rematches():
    m = Menu(["foo", "foo bar"])
    m.insert("foo bar")
    m.delete_word_back()
    assert m.matches == ["foo", "foo bar"]


def test_delete_word_back_treats_every_delimiter_character_as_a_delimiter():
    m = Menu(["a"], word_delimiters=" -/")
    m.text, m.cursor = "--b", 2
    m.delete_word_back()
    assert (m.text, m.cursor) == ("b", 0)


def test_delete_word_back_with_several_delimiter_characters_and_a_tail():
    m = Menu(["a"], word_delimiters="/ ")
    m.text, m.cursor = "-b  a", 4
    m.delete_word_back()
    assert (m.text, m.cursor) == ("a", 0)


def test_delete_removes_the_character_at_the_cursor_and_does_nothing_at_the_end():
    m = Menu(["a"])
    m.insert("abc")
    m.cursor = 1
    m.delete()
    assert (m.text, m.cursor) == ("ac", 1)
    m.cursor = 2
    m.delete()
    assert m.text == "ac"


def test_delete_word_back_removes_trailing_word_then_the_gap():
    m = Menu(["a"])
    m.insert("foo bar baz")
    m.delete_word_back()
    assert (m.text, m.cursor) == ("foo bar ", 8)
    m.delete_word_back()
    assert (m.text, m.cursor) == ("foo ", 4)


def test_delete_word_back_respects_configured_delimiters():
    m = Menu(["a"], word_delimiters="/ ")
    m.insert("usr/local/bin")
    m.delete_word_back()
    assert m.text == "usr/local/"


def test_delete_to_end_and_to_start():
    m = Menu(["a"])
    m.insert("hello world")
    m.cursor = 5
    m.delete_to_end()
    assert (m.text, m.cursor) == ("hello", 5)
    m.insert(" there")
    m.cursor = 5
    m.delete_to_start()
    assert (m.text, m.cursor) == (" there", 0)


def test_word_movement():
    m = Menu(["a"])
    m.insert("foo bar baz")
    stops = []
    for _ in range(3):
        m.word_left()
        stops.append(m.cursor)
    assert stops == [8, 4, 0]
    stops = []
    for _ in range(3):
        m.word_right()
        stops.append(m.cursor)
    assert stops == [3, 7, 11]


# --- 2b: selection and paging -----------------------------------------------------------


def test_select_next_flips_to_the_next_page_when_leaving_the_current_one():
    m = numbered(8, per_page=3)
    for _ in range(3):
        m.select_next()
    assert (m.sel, m.page_start, m.page()) == (3, 3, ["i3", "i4", "i5"])


def test_select_prev_flips_back_to_the_previous_page():
    m = numbered(8, per_page=3)
    for _ in range(3):
        m.select_next()
    m.select_prev()
    assert (m.sel, m.page_start) == (2, 0)


def test_selection_stops_at_both_ends():
    m = numbered(2, per_page=3)
    m.select_prev()
    assert m.sel == 0
    m.select_next()
    m.select_next()
    assert m.sel == 1


def test_page_next_and_prev_select_the_first_item_of_the_page():
    m = numbered(8, per_page=3)
    m.page_next()
    assert (m.sel, m.page_start) == (3, 3)
    m.page_next()
    assert (m.sel, m.page_start, m.page()) == (6, 6, ["i6", "i7"])
    m.page_next()  # no next page
    assert (m.sel, m.page_start) == (6, 6)
    m.page_prev()
    assert (m.sel, m.page_start) == (3, 3)
    m.page_prev()
    m.page_prev()  # no previous page
    assert (m.sel, m.page_start) == (0, 0)


def test_end_moves_the_cursor_first_then_jumps_to_the_last_match():
    m = numbered(8, per_page=3)
    m.insert("i")
    m.cursor = 0
    m.end()
    assert m.cursor == 1 and m.sel == 0  # first press: only the cursor moves
    m.end()
    assert (m.sel, m.page_start, m.page()) == (7, 5, ["i5", "i6", "i7"])


def test_end_when_everything_fits_just_selects_the_last_match():
    m = numbered(3, per_page=5)
    m.end()
    assert (m.sel, m.page_start) == (2, 0)


def test_home_selects_the_first_match_then_moves_the_cursor():
    m = numbered(8, per_page=3)
    m.insert("i")
    for _ in range(4):
        m.select_next()
    m.home()
    assert (m.sel, m.page_start, m.cursor) == (0, 0, 1)  # first press: the list
    m.home()
    assert m.cursor == 0  # second press: the cursor


def test_left_moves_the_cursor_when_the_first_match_is_selected():
    m = numbered(3)
    m.insert("i")
    m.left()
    assert (m.cursor, m.sel) == (0, 0)


def test_left_steps_back_through_the_list_in_a_horizontal_menu():
    m = numbered(3)
    m.insert("i")
    m.select_next()
    m.left()
    assert (m.cursor, m.sel) == (1, 0)


def test_in_a_vertical_menu_left_and_right_only_move_the_cursor():
    m = numbered(3, lines=3)
    m.insert("i")
    m.select_next()
    m.left()
    assert (m.cursor, m.sel) == (0, 1)
    m.left()  # at the start of the text: nothing, not a list move
    assert (m.cursor, m.sel) == (0, 1)
    m.cursor = 1
    m.right()  # at the end of the text: nothing, not a list move
    assert (m.cursor, m.sel) == (1, 1)


def test_right_moves_the_cursor_while_there_is_text_to_the_right():
    m = numbered(3)
    m.insert("i")
    m.cursor = 0
    m.right()
    assert (m.cursor, m.sel) == (1, 0)


def test_right_at_the_end_of_the_text_steps_forward_through_the_list():
    m = numbered(3)
    m.insert("i")  # the cursor is now at the end of the text
    m.right()
    assert (m.cursor, m.sel) == (1, 1)


def test_complete_copies_the_selected_match_into_the_input():
    m = Menu(["apple", "apricot"])
    m.insert("ap")
    m.select_next()
    m.complete()
    assert (m.text, m.cursor) == ("apricot", 7)
    assert m.matches == ["apricot"]


def test_complete_with_nothing_selected_does_nothing():
    m = Menu(["a"])
    m.insert("zzz")
    m.complete()
    assert m.text == "zzz"


# --- 2c: finishing ----------------------------------------------------------------------


def test_accept_returns_the_selected_match_and_closes():
    m = Menu(["alpha", "beta"])
    assert m.accept() == Choice("alpha", True)


def test_accept_with_shift_returns_what_was_typed():
    m = Menu(["alpha", "beta"])
    m.insert("al")
    assert m.accept(shift=True) == Choice("al", True)


def test_accept_with_nothing_matching_returns_the_typed_text():
    m = Menu(["alpha"])
    m.insert("zzz")
    assert m.accept() == Choice("zzz", True)


def test_accept_with_ctrl_keeps_the_menu_open_and_marks_the_item():
    m = Menu(["alpha", "beta"])
    m.select_next()
    assert m.accept(ctrl=True) == Choice("beta", False)
    assert m.marked == {"beta"}


def test_accept_with_ctrl_and_nothing_selected_marks_nothing():
    m = Menu(["alpha"])
    m.insert("zzz")
    assert m.accept(ctrl=True) == Choice("zzz", False)
    assert m.marked == set()


def test_cancel_sets_the_flag():
    m = Menu(["a"])
    assert not m.cancelled
    m.cancel()
    assert m.cancelled


@pytest.mark.parametrize(
    "method", ["select_next", "select_prev", "page_next", "page_prev", "complete", "home", "end"]
)
def test_navigation_on_an_empty_menu_never_crashes(method):
    getattr(Menu([]), method)()
