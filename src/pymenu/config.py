"""Defaults, the equivalent of dmenu's config.def.h. Command-line flags override them.

Colours are 0xRRGGBB integers. The three schemes are dmenu's: normal, selected, and "out"
(an item you marked with Ctrl+Return, which keeps the menu open).
"""

from dataclasses import dataclass, field

TOPBAR = True  # -b puts the menu at the bottom instead
FONT = "Menlo:size=13"  # -fn  ("Name:size=N", or just "Name")
PROMPT = None  # -p   text shown to the left of the input field
LINES = 0  # -l   0 = items in one horizontal row; N = a vertical list with N lines
CENTER = False  # -c   centre the menu on the screen instead of spanning its top (or bottom) edge
WIDTH = 700  # -W   width in points when centred (never more than 90% of the screen)
CENTER_LINES = 10  # -c without -l shows this many lines: a centred menu reads best as a list
WORD_DELIMITERS = " "  # characters that are not part of a word (for Alt+b/f and Ctrl+w)

COLORS = {
    "norm_fg": 0xBBBBBB,
    "norm_bg": 0x222222,
    "sel_fg": 0xEEEEEE,
    "sel_bg": 0x005577,
    "out_fg": 0x000000,
    "out_bg": 0x00FFFF,
}


@dataclass
class Settings:
    """Everything the menu needs to know, after the command line has been applied to the defaults."""

    topbar: bool = TOPBAR
    font: str = FONT
    prompt: str | None = PROMPT
    lines: int = LINES
    center: bool = CENTER  # -c
    width: int = WIDTH  # -W
    monitor: int = -1  # -m  which monitor (-1: the one under the pointer)
    ignore_case: bool = False  # -i
    fast: bool = False  # -f  accepted for compatibility; dmenu uses it to grab the keyboard earlier
    embed: int | None = None  # -w  embedding in another window: not possible on macOS, accepted and ignored
    word_delimiters: str = WORD_DELIMITERS
    colors: dict[str, int] = field(default_factory=lambda: dict(COLORS))
