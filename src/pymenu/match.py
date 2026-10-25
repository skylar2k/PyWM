"""STEP 1: dmenu's `match()`: which items survive what you have typed, and in what order.

This is dmenu's whole "intelligence", and it is a pure function: no window, no keyboard, nothing
to mock. Port it from `match()` in dmenu.c (https://git.suckless.org/dmenu/file/dmenu.c.html).
"""

from collections.abc import Sequence
from itertools import chain


def match(items: Sequence[str], text: str, *, ignore_case: bool = False) -> list[str]:
    """Return the items matching `text`, best first.

    Rules (dmenu's):

    * Split `text` on spaces into *tokens*. Runs of spaces and leading/trailing spaces make no
      empty tokens. An item matches only if **every** token occurs somewhere inside it.
    * With no tokens at all (empty text, or only spaces), every item matches.
    * Matches come out in three groups, each keeping the items' original relative order:
        1. **exact**: the item is identical to `text` (the raw text, spaces and all).
           With no tokens, all items count as exact.
        2. **prefix**: the item starts with the *first* token.
        3. **substring**: everything else that matched.
    * `ignore_case=True` makes all three comparisons case-insensitive (dmenu's `-i`).

    Examples:  match(["xfire", "firefox", "fire", "campfire"], "fire")
               == ["fire", "firefox", "xfire", "campfire"]
    """
    # A function, chosen once, instead of an `if ignore_case` at every comparison below.
    fold = str.casefold if ignore_case else str
    needle = fold(text)
    tokens = [t for t in needle.split(" ") if t]
    if not tokens:
        return list(items)  # a copy, never the caller's own object

    def rank(haystack: str) -> int:
        """0: exact, 1: starts with the first token, 2: contains the tokens somewhere else."""
        if haystack == needle:
            return 0
        return 1 if haystack.startswith(tokens[0]) else 2

    # Deciding the rank (above) is kept apart from collecting by rank (here).
    buckets: tuple[list[str], list[str], list[str]] = ([], [], [])
    for item in items:
        haystack = fold(item)
        if all(token in haystack for token in tokens):  # a generator: stops at the first miss
            buckets[rank(haystack)].append(item)
    return [*chain.from_iterable(buckets)]
