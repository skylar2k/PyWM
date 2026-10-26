"""STEP 2: the menu's state machine: what you typed, where the cursor is, which match is selected.

Pure Python, no window and no keyboard: key presses reach it only as method calls (see keys.py), and
the view only reads its attributes. That is what lets every method here be tested without a screen.

The semantics below are dmenu's. Each docstring says which key of dmenu.c's `keypress()` it serves.
"""

from dataclasses import dataclass

from pymenu.match import match


def _word_start(before: str, delimiters: str) -> int:
    """Index where the word that ends `before` starts, after skipping trailing delimiters."""
    p = len(before.rstrip(delimiters))
    while p > 0 and before[p - 1] not in delimiters:
        p -= 1
    return p


def _word_end(after: str, delimiters: str) -> int:
    """Distance from the start of `after``, which is where the cursor is"""
    p = len(after) - len(after.lstrip(delimiters))
    while p < len(after) and after[p] not in delimiters:
        p += 1
    return p


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
        self.text = self.text[: self.cursor] + s + self.text[self.cursor :]
        self.cursor = self.cursor + len(s)
        self.rematch()

    def backspace(self) -> None:
        """Delete the character before the cursor (nothing at the start of the text), then rematch."""
        if not self.cursor:
            return
        self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
        self.cursor = self.cursor - 1
        self.rematch()

    def delete(self) -> None:
        """Delete the character at the cursor (nothing at the end of the text), then rematch."""
        if self.cursor >= len(self.text):
            return
        self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]
        self.rematch()

    def delete_word_back(self) -> None:
        """Ctrl+w: delete delimiter characters before the cursor, then the word characters before those.

        "foo bar baz" with the cursor at the end becomes "foo bar "; again, "foo ". A character is a
        delimiter if it occurs in `self.word_delimiters`.
        """
        before, after = self.text[: self.cursor], self.text[self.cursor :]
        kept = _word_start(before, self.word_delimiters)
        self.text, self.cursor = before[:kept] + after, kept
        self.rematch()

    def delete_to_end(self) -> None:
        """Ctrl+k: delete everything from the cursor to the end of the text, then rematch."""
        self.text = self.text[: self.cursor]
        self.rematch()

    def delete_to_start(self) -> None:
        """Ctrl+u: delete everything before the cursor (the cursor goes to 0), then rematch."""
        self.text = self.text[self.cursor :]
        self.cursor = 0
        self.rematch()

    def word_left(self) -> None:
        """Alt+b / Ctrl+Left: move to the start of the word before the cursor (skip delimiters first)."""
        before = self.text[: self.cursor]
        self.cursor = _word_start(before, self.word_delimiters)

    def word_right(self) -> None:
        """Alt+f / Ctrl+Right: move to the end of the next word (skip delimiters first)."""
        after = self.text[self.cursor :]
        self.cursor += _word_end(after, self.word_delimiters)

    # ------------------------------------------------------------------ 2b: selection and paging

    def select_next(self) -> None:
        """Down: select the next match. Stepping past the last item on the page makes that item the
        first of the next page (`page_start = sel`). Does nothing on the last match."""
        next_page = self.page_start + self.per_page

        # No selection or going out of bounds
        if self.sel is None or self.sel + 1 >= len(self.matches):
            return
        self.sel += 1
        if self.sel >= next_page:
            self.page_start = self.sel

    def select_prev(self) -> None:
        """Up: select the previous match. Stepping before the first item on the page shows the
        previous page (`page_start` goes back by `per_page`, not below 0). Nothing on the first match."""
        previous_page = max(0, self.page_start - self.per_page)
        if self.sel is None or self.sel <= 0:
            return
        self.sel -= 1
        if self.sel < self.page_start:
            self.page_start = previous_page

    def page_next(self) -> None:
        """Page Down: the next page, with its first item selected."""
        # Empty menu or nothing selected
        if self.sel is None:
            return

        next_page = self.page_start + self.per_page
        # No next page: If next page is more than the length of matches
        if next_page >= len(self.matches):
            return

        self.sel = self.page_start = next_page

    def page_prev(self) -> None:
        """Page Up: show the previous page and select its first item.

        On the first page there is no previous page, but dmenu still selects that page's first item
        (`sel = page_start = 0`), so this does the same. `page_start` never goes below 0.
        """
        # Empty menu or nothing selected
        if self.sel is None:
            return

        previous_page = max(0, self.page_start - self.per_page)
        self.sel = self.page_start = previous_page

    def left(self) -> None:
        """The Left arrow, which does two jobs in dmenu.

        If the cursor is not at the start of the text AND (nothing or the first match is selected,
        OR the list is vertical (`lines > 0`)): move the cursor left one character.
        Otherwise, in a vertical list do nothing; in a horizontal one act like `select_prev`.
        """
        if self.cursor > 0 and (self.sel is None or self.sel == 0 or self.lines > 0):
            self.cursor -= 1
            return
        # Vertical list
        if self.lines > 0:
            return
        self.select_prev()

    def right(self) -> None:
        """The Right arrow: if the cursor is not at the end of the text, move it right one character.
        At the end of the text: nothing in a vertical list, `select_next` in a horizontal one."""
        if self.cursor < len(self.text):
            self.cursor += 1
            return
        # Vertical list
        if self.lines > 0:
            return
        self.select_next()

    def home(self) -> None:
        """Home, which does two jobs: if nothing or the first match is selected, move the cursor to 0;
        otherwise select the first match and show the first page."""
        if self.sel is None or self.sel == 0:
            self.cursor = 0
        else:
            self.sel = self.page_start = 0

    def end(self) -> None:
        """End, two jobs: if the cursor is not at the end of the text, move it there. Otherwise select
        the last match; if that is not on the visible page, show the last full page
        (`page_start = max(0, len(matches) - per_page)`)."""
        if self.cursor != len(self.text):
            self.cursor = len(self.text)
            return
        # No matches, so nothing to do
        if self.sel is None:
            return

        self.sel = len(self.matches) - 1
        # Only if the last match is off the current page, show the last full page (dmenu: `if (next)`)
        if self.sel >= self.page_start + self.per_page:
            self.page_start = max(0, len(self.matches) - self.per_page)

    def complete(self) -> None:
        """Tab: copy the selected match into the input (cursor at its end) and rematch. Nothing if
        no match is selected."""
        # No matches, so nothing to complete with
        if self.sel is None:
            return
        self.text = self.matches[self.sel]
        self.cursor = len(self.text)
        self.rematch()

    # ------------------------------------------------------------------ 2c: finishing

    def accept(self, *, shift: bool = False, ctrl: bool = False) -> Choice:
        """Return.

        * The output is the selected match, unless `shift` is held or nothing is selected: then it
          is the text you typed (this is how a script gets free-form input).
        * Without `ctrl` the menu closes.
        * With `ctrl` it stays open, and the selected match (if any) is added to `self.marked`.
        """
        # What a script receives: the selected match, or the typed text (Shift, or no match to choose)
        output = self.text if self.sel is None or shift else self.matches[self.sel]
        if not ctrl:
            return Choice(output, close=True)
        # Ctrl+Return keeps the menu open and marks the item
        if self.sel is not None:
            self.marked.add(self.matches[self.sel])
        return Choice(output, close=False)

    def cancel(self) -> None:
        """Escape / Ctrl+c / Ctrl+g: set `self.cancelled`."""
        self.cancelled = True
