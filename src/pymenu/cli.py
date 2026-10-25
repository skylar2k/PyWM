"""The command line: dmenu's flags, reading items from stdin, and the exit status.

This file is finished: it is plumbing, not the point of the exercise. The contract it implements:

    stdin  -> one item per line
    stdout <- the chosen item (or, if nothing matched, whatever you typed), one line per choice
    exit 0 -> something was chosen        exit 1 -> cancelled (Escape)
"""

import argparse
import sys
from typing import TextIO

from pymenu.config import Settings

VERSION = "0.1.0"


def parse_color(text: str) -> int:
    """'#rrggbb' (the '#' is optional) -> 0xRRGGBB."""
    digits = text.removeprefix("#")
    try:
        if len(digits) != 6:
            raise ValueError
        return int(digits, 16)
    except ValueError:
        raise argparse.ArgumentTypeError(f"cannot parse colour {text!r} (expected #rrggbb)") from None


def build_parser() -> argparse.ArgumentParser:
    # dmenu's options are single-dash and several letters long (-fn, -nb ...), so no abbreviations.
    p = argparse.ArgumentParser(prog="pymenu", allow_abbrev=False, description="dynamic menu for macOS")
    p.add_argument("-v", action="version", version=f"pymenu-{VERSION}", help="print version and exit")
    p.add_argument("-b", dest="bottom", action="store_true", help="show the menu at the bottom of the screen")
    p.add_argument("-f", dest="fast", action="store_true", help="accepted for compatibility (no effect)")
    p.add_argument("-i", dest="ignore_case", action="store_true", help="match case-insensitively")
    p.add_argument("-l", dest="lines", type=int, metavar="LINES", help="vertical list with this many lines")
    p.add_argument(
        "-m", dest="monitor", type=int, metavar="N", help="show on monitor N (default: under the pointer)"
    )
    p.add_argument("-p", dest="prompt", metavar="PROMPT", help="text to the left of the input field")
    p.add_argument("-fn", dest="font", metavar="FONT", help='font, e.g. "Menlo:size=14"')
    for flag, key, what in (
        ("-nb", "norm_bg", "normal background"),
        ("-nf", "norm_fg", "normal foreground"),
        ("-sb", "sel_bg", "selected background"),
        ("-sf", "sel_fg", "selected foreground"),
        ("-ob", "out_bg", "marked-item background"),
        ("-of", "out_fg", "marked-item foreground"),
    ):
        p.add_argument(flag, dest=key, type=parse_color, metavar="COLOR", help=f"{what} colour")
    p.add_argument("-w", dest="embed", type=lambda s: int(s, 0), metavar="ID", help="ignored on macOS")
    return p


def parse(argv: list[str] | None = None) -> Settings:
    """Apply the command line on top of config.py's defaults."""
    args = build_parser().parse_args(argv)
    settings = Settings()
    settings.topbar = not args.bottom
    settings.fast = args.fast
    settings.ignore_case = args.ignore_case
    settings.embed = args.embed
    if args.lines is not None:
        settings.lines = max(0, args.lines)
    if args.monitor is not None:
        settings.monitor = args.monitor
    if args.prompt is not None:
        settings.prompt = args.prompt
    if args.font is not None:
        settings.font = args.font
    for key in settings.colors:
        if (value := getattr(args, key)) is not None:
            settings.colors[key] = value
    return settings


def read_items(stream: TextIO) -> list[str]:
    """One item per line. An empty stdin is fine: the menu is then a plain text prompt."""
    lines = stream.read().split("\n")
    if lines and lines[-1] == "":  # the newline that ends the last line is not another item
        lines.pop()
    return lines


def emit(text: str) -> None:
    """Print one choice immediately (Ctrl+Return prints without closing the menu)."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    settings = parse(argv)
    items = read_items(sys.stdin)
    from pymenu import app  # late: AppKit is only needed once a window is really going to appear

    return app.run(items, settings, emit)
