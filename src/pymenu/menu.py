"""STEP 2: the menu's state machine: what you typed, where the cursor is, which match is selected.

Pure Python, no window and no keyboard: key presses reach it only as method calls (see keys.py), and
the view only reads its attributes. That is what lets every method here be tested without a screen.

The semantics below are dmenu's. Each docstring says which key of dmenu.c's `keypress()` it serves.
"""

from dataclasses import dataclass

from pymenu.match import match


@dataclass
class Choice:
    """What accepting (Return) produced: the text to print, and whether the menu should close."""

    output: str
    close: bool


class Menu:
    def __init__(
        self,
        items: list[str],
        *,
        ignore_case: bool = False,
        lines: int = 0,
        per_page: int | None = None,
        word_delimiters: str = " ",
    ) -> None:
        self.items = list(items)
        self.ignore_case = ignore_case
        self.lines = lines  # 0: horizontal row of items; N: vertical list of N lines
        self.per_page = per_page or lines or 10  # how many matches fit on one page
        self.word_delimiters = word_delimiters

        self.text = ""  # what has been typed
        self.cursor = 0  # insertion point: 0..len(text)
        self.matches: list[str] = []  # items matching `text`, best first (see match.py)
        self.sel: int | None = None  # index into `matches` of the selected item; None if no matches
        self.page_start = 0  # index into `matches` of the first item on the visible page
        self.marked: set[str] = set()  # items marked with Ctrl+Return (dmenu's "out" scheme)
        self.cancelled = False
        self.rematch()

    # ------------------------------------------------------------------ provided plumbing

    def rematch(self) -> None:
        """Recompute `matches` for the current text and reset selection and paging."""
        self.matches = match(self.items, self.text, ignore_case=self.ignore_case)
        self.sel = 0 if self.matches else None
        self.page_start = 0

    def page(self) -> list[str]:
        """The matches on the visible page; this is what the view draws."""
        return self.matches[self.page_start : self.page_start + self.per_page]

    # ------------------------------------------------------------------ 2a: editing the text

    def insert(self, s: str) -> None:
        """Insert `s` at the cursor, move the cursor after it, and rematch."""
        raise NotImplementedError("step 2a: Menu.insert")

    def backspace(self) -> None:
        """Delete the character before the cursor (nothing at the start of the text), then rematch."""
        raise NotImplementedError("step 2a: Menu.backspace")

    def delete(self) -> None:
        """Delete the character at the cursor (nothing at the end of the text), then rematch."""
        raise NotImplementedError("step 2a: Menu.delete")

    def delete_word_back(self) -> None:
        """Ctrl+w: delete delimiter characters before the cursor, then the word characters before those.

        "foo bar baz" with the cursor at the end becomes "foo bar "; again, "foo ". A character is a
        delimiter if it occurs in `self.word_delimiters`.
        """
        raise NotImplementedError("step 2a: Menu.delete_word_back")

    def delete_to_end(self) -> None:
        """Ctrl+k: delete everything from the cursor to the end of the text, then rematch."""
        raise NotImplementedError("step 2a: Menu.delete_to_end")

    def delete_to_start(self) -> None:
        """Ctrl+u: delete everything before the cursor (the cursor goes to 0), then rematch."""
        raise NotImplementedError("step 2a: Menu.delete_to_start")

    def word_left(self) -> None:
        """Alt+b / Ctrl+Left: move to the start of the word before the cursor (skip delimiters first)."""
        raise NotImplementedError("step 2a: Menu.word_left")

    def word_right(self) -> None:
        """Alt+f / Ctrl+Right: move to the end of the next word (skip delimiters first)."""
        raise NotImplementedError("step 2a: Menu.word_right")

    # ------------------------------------------------------------------ 2b: selection and paging

    def select_next(self) -> None:
        """Down: select the next match. Stepping past the last item on the page makes that item the
        first of the next page (`page_start = sel`). Does nothing on the last match."""
        raise NotImplementedError("step 2b: Menu.select_next")

    def select_prev(self) -> None:
        """Up: select the previous match. Stepping before the first item on the page shows the
        previous page (`page_start` goes back by `per_page`, not below 0). Nothing on the first match."""
        raise NotImplementedError("step 2b: Menu.select_prev")

    def page_next(self) -> None:
        """Page Down: the next page, with its first item selected. Nothing if there is no next page."""
        raise NotImplementedError("step 2b: Menu.page_next")

    def page_prev(self) -> None:
        """Page Up: the previous page, with its first item selected. Nothing on the first page."""
        raise NotImplementedError("step 2b: Menu.page_prev")

    def left(self) -> None:
        """The Left arrow, which does two jobs in dmenu.

        If the cursor is not at the start of the text AND (nothing or the first match is selected,
        OR the list is vertical (`lines > 0`)): move the cursor left one character.
        Otherwise, in a vertical list do nothing; in a horizontal one act like `select_prev`.
        """
        raise NotImplementedError("step 2b: Menu.left")

    def right(self) -> None:
        """The Right arrow: if the cursor is not at the end of the text, move it right one character.
        At the end of the text: nothing in a vertical list, `select_next` in a horizontal one."""
        raise NotImplementedError("step 2b: Menu.right")

    def home(self) -> None:
        """Home, which does two jobs: if nothing or the first match is selected, move the cursor to 0;
        otherwise select the first match and show the first page."""
        raise NotImplementedError("step 2b: Menu.home")

    def end(self) -> None:
        """End, two jobs: if the cursor is not at the end of the text, move it there. Otherwise select
        the last match; if that is not on the visible page, show the last full page
        (`page_start = max(0, len(matches) - per_page)`)."""
        raise NotImplementedError("step 2b: Menu.end")

    def complete(self) -> None:
        """Tab: copy the selected match into the input (cursor at its end) and rematch. Nothing if
        no match is selected."""
        raise NotImplementedError("step 2b: Menu.complete")

    # ------------------------------------------------------------------ 2c: finishing

    def accept(self, *, shift: bool = False, ctrl: bool = False) -> Choice:
        """Return.

        * The output is the selected match, unless `shift` is held or nothing is selected: then it
          is the text you typed (this is how a script gets free-form input).
        * Without `ctrl` the menu closes.
        * With `ctrl` it stays open, and the selected match (if any) is added to `self.marked`.
        """
        raise NotImplementedError("step 2c: Menu.accept")

    def cancel(self) -> None:
        """Escape / Ctrl+c / Ctrl+g: set `self.cancelled`."""
        raise NotImplementedError("step 2c: Menu.cancel")
