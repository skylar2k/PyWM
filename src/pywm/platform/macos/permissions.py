"""The two permissions pywm needs.

Accessibility    lets us read and move other apps' windows.
Input Monitoring lets the event tap see key presses, so Option+key can be a hotkey.

macOS grants these to a *program*, and for a command-line tool that means the terminal (or app)
that launched it, e.g. Terminal, iTerm2 or Ghostty.
"""

from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess


def ensure_accessibility() -> bool:
    """True if granted. If not, macOS shows its permission dialog."""
    return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))


def ensure_input_monitoring() -> bool:
    return bool(CGPreflightListenEventAccess() or CGRequestListenEventAccess())
