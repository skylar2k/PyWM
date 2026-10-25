"""STEP 5: the window and the event loop: dmenu's `setup()` and `run()`.

`run_menu` shows the menu, feeds key presses to `keys.dispatch`, redraws after each one, prints
choices with `emit`, and returns the exit status (0 chosen, 1 cancelled).

What it has to do (the order matters):

1. `NSApplication.sharedApplication()` with the *accessory* activation policy (no Dock icon).
2. A borderless NSPanel across the top (or bottom with -b) of a monitor, one line tall plus one
   line per `lines`. Which monitor: `settings.monitor`, or the one under the pointer
   (`NSEvent.mouseLocation()` and `NSScreen.screens()`). AppKit's y axis points UP.
   A borderless window only takes keys if a subclass overrides `canBecomeKeyWindow` to return True.
3. Put a `MenuView` in it, make the panel key and order it front, and **activate the app**.
   Run it with `AppHelper.runEventLoop()` (a real `NSApplication.run()`); the lighter
   `runConsoleEventLoop` does not dispatch activation or key-window changes, so the window never
   receives keys. Neither needs any macOS permission: this is your own window receiving keys.
4. Turn key events into `KeyPress` (override `keyDown_` in a view or the panel): `event.keyCode()`
   identifies the physical key, `event.characters()` is the typed text, `event.modifierFlags()` has
   the Shift/Control/Option bits. Call `dispatch`, `view.setNeedsDisplay_(True)`, and when it returns
   a Choice call `emit(choice.output)`; if `choice.close` or `menu.cancelled`, stop the loop.
5. Return 0 if something was chosen, 1 if cancelled. dmenu prints on every Return, so a script can
   read several lines with Ctrl+Return.

For paste (Ctrl+y) read `NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)`.
"""

from collections.abc import Callable

from pymenu.config import Settings
from pymenu.menu import Menu


def run_menu(menu: Menu, settings: Settings, emit: Callable[[str], None]) -> int:
    raise NotImplementedError("step 5: create the panel, run the event loop; see this file's docstring")
