"""The glue: build the menu, hand it to the window, return the exit status. Finished plumbing."""

from collections.abc import Callable

from pymenu.config import Settings
from pymenu.menu import Menu


def run(items: list[str], settings: Settings, emit: Callable[[str], None]) -> int:
    """Show the menu and block until it is closed. Returns the process exit status (0 chosen, 1 cancelled)."""
    from pymenu.macos.window import run_menu  # AppKit lives behind this import

    menu = Menu(
        items,
        ignore_case=settings.ignore_case,
        lines=settings.lines,
        word_delimiters=settings.word_delimiters,
    )
    return run_menu(menu, settings, emit)
