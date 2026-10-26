"""Invariants of `Menu`: facts that must be true after EVERY operation, whatever came before.

A failing example test says "this input gives the wrong output". A failing invariant test says
"some sequence of keys leaves the menu in a state that can never be right", and it tells you the
sequence. The operations are applied at random (with fixed seeds, so a failure is reproducible),
and `check` runs after each one.

The four invariants:

1. the cursor is inside the text:                 0 <= cursor <= len(text)
2. `matches` is never stale:                      matches == match(items, text)
3. `sel` is None exactly when nothing matches,    otherwise it is a valid index into `matches`
4. the selection is on the visible page:          page_start <= sel < page_start + per_page
"""

import random

import pytest

from pymenu.match import match
from pymenu.menu import Menu

OPERATIONS = [
    "insert",
    "backspace",
    "delete",
    "delete_word_back",
    "delete_to_end",
    "delete_to_start",
    "word_left",
    "word_right",
    "select_next",
    "select_prev",
    "page_next",
    "page_prev",
    "home",
    "end",
    "left",
    "right",
    "complete",
    "jump_cursor",  # not a Menu method: the cursor can be put anywhere valid (keys, mouse, tests)
]


def check(m: Menu, trail: list[str]) -> None:
    where = (
        f"after {trail[-6:]}: text={m.text!r} cursor={m.cursor} sel={m.sel} "
        f"page_start={m.page_start} per_page={m.per_page} lines={m.lines} matches={len(m.matches)}"
    )
    assert 0 <= m.cursor <= len(m.text), f"cursor is outside the text ({where})"
    assert m.matches == match(m.items, m.text, ignore_case=m.ignore_case), f"matches are stale ({where})"
    assert (m.sel is None) == (not m.matches), f"sel must be None exactly when nothing matches ({where})"
    assert m.page_start >= 0, f"page_start is negative ({where})"
    if m.sel is not None:
        assert 0 <= m.sel < len(m.matches), f"sel points outside the matches ({where})"
        assert m.page_start <= m.sel < m.page_start + m.per_page, f"sel is not on the visible page ({where})"


def random_menu(rng: random.Random) -> Menu:
    items = ["".join(rng.choice("ab -") for _ in range(rng.randint(0, 6))) for _ in range(rng.randint(0, 10))]
    lines = rng.choice([0, rng.randint(1, 4)])  # 0: a horizontal row; N: a vertical list of N lines
    return Menu(
        items,
        ignore_case=rng.random() < 0.5,
        lines=lines,
        per_page=lines or rng.randint(1, 4),
        word_delimiters=rng.choice([" ", " -"]),
    )


def apply(m: Menu, operation: str, rng: random.Random) -> None:
    if operation == "insert":
        m.insert(rng.choice(["a", "b", " ", "ab", "-", ""]))
    elif operation == "jump_cursor":
        m.cursor = rng.randint(0, len(m.text))
    else:
        getattr(m, operation)()


@pytest.mark.parametrize("seed", range(20))
def test_invariants_hold_after_every_random_operation(seed):
    rng = random.Random(seed)
    for _ in range(40):
        m = random_menu(rng)
        check(m, [])  # a freshly built menu must already satisfy them
        trail: list[str] = []
        for _ in range(25):
            operation = rng.choice(OPERATIONS)
            trail.append(operation)
            apply(m, operation, rng)
            check(m, trail)
