"""STEP 5: the window and the event loop: dmenu's `setup()` and `run()`.

`run_menu` shows the menu, feeds key presses to `keys.dispatch`, redraws after each one, prints
choices with `emit`, and returns the exit status (0 chosen, 1 cancelled).

Four things in here are worth understanding, because each one is a small AppKit lesson:

1. **An accessory app.** `setActivationPolicy_(Accessory)` means no Dock icon and no menu bar of
   our own: pymenu is a tool that appears, is used, and disappears.

2. **A borderless window only takes keys if it says so.** The default answer of a borderless
   `NSPanel` to `canBecomeKeyWindow` is "no", so `_Panel` overrides it. Without that the menu would
   show but never receive a key press.

3. **A real event loop.** We call `NSApplication.run()`. The lighter run loops (such as PyObjC's
   `runConsoleEventLoop`) do not dispatch the activation and key-window events a window needs.
   Neither Accessibility nor Input Monitoring is needed: these are keys sent to *our own* window.

4. **Stopping `run()` from the inside.** `app.stop_(None)` only takes effect once the loop handles
   its next event, so `_stop_event_loop` also posts a harmless dummy event to wake it up. The
   alternative, terminating the process from inside AppKit, would skip Python's stdout flush and
   lose our exit status.

Reading order: `run_menu` (the story), then `_Session` (what happens on each key), then the small
helpers.
"""

import heapq
import sys
from collections.abc import Callable

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSEvent,
    NSEventTypeApplicationDefined,
    NSPanel,
    NSPasteboard,
    NSPasteboardTypeString,
    NSScreen,
    NSStatusWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSMakeRect, NSObject
from PyObjCTools import AppHelper

from pymenu.config import Settings
from pymenu.keys import dispatch
from pymenu.macos.events import to_keypress
from pymenu.macos.view import MenuView, Style, cell_width, make_style, make_view
from pymenu.menu import Menu

type Rect = tuple[float, float, float, float]  # x, y, width, height


# --------------------------------------------------------------------------- the story


def run_menu(menu: Menu, settings: Settings, emit: Callable[[str], None]) -> int:
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon

    style = make_style(settings)
    menu.lines = min(menu.lines, len(menu.items))  # dmenu: more lines than items makes no sense
    screen = pick_screen(settings.monitor)
    frame = screen.frame()
    width = frame.size.width
    menu.per_page = menu.lines or fit_per_page(menu, settings, style, width)

    height = (menu.lines + 1) * style.bh
    rect = menu_rect((frame.origin.x, frame.origin.y, width, frame.size.height), height, settings.topbar)

    session = _Session(menu, emit, app)
    session.view = make_view(width, menu, settings, style, _InputView)
    session.view.session = session
    session.panel = _make_panel(rect, session)

    # The delegate is told when the app has finished launching; that is the right moment to show
    # the window and take keyboard focus. NSApplication holds its delegate weakly, so we keep
    # `delegate` alive in this variable for as long as `app.run()` runs.
    delegate = _Delegate.alloc().init()
    delegate.session = session
    app.setDelegate_(delegate)

    app.run()  # blocks until `_stop_event_loop` ends it
    return session.status


# --------------------------------------------------------------------------- what happens on each key


class _Session:
    """Everything that changes while the menu is open. One object, so the story is easy to follow."""

    def __init__(self, menu: Menu, emit: Callable[[str], None], app: NSApplication) -> None:
        self.menu, self.emit, self.app = menu, emit, app
        self.view: MenuView
        self.panel: NSPanel
        self.status = 1  # "cancelled", until something is chosen
        self.finished = False

    def show(self) -> None:
        """Order the window in, make it the key window, and make our app the active one."""
        self.panel.makeKeyAndOrderFront_(None)
        self.panel.makeFirstResponder_(self.view)
        if hasattr(self.app, "activate"):  # macOS 14 and later
            self.app.activate()
        else:
            self.app.activateIgnoringOtherApps_(True)
        # If macOS refuses to give us the keyboard we would sit here ignoring every key, so say so.
        AppHelper.callLater(0.5, self._warn_if_not_key)

    def _warn_if_not_key(self) -> None:
        if not self.panel.isKeyWindow():
            message = "pymenu: could not take the keyboard focus; keys will not reach the menu"
            print(message, file=sys.stderr)

    def on_key(self, event: NSEvent) -> None:
        """One key press: translate it, apply it to the menu, then either finish or redraw."""
        press = to_keypress(int(event.keyCode()), int(event.modifierFlags()), str(event.characters() or ""))
        if press is None:
            return
        choice = dispatch(self.menu, press, paste=read_clipboard)
        if choice is not None:
            self.emit(choice.output)  # printed (and flushed) at once, like dmenu's puts()
            if choice.close:
                self.status = 0
        if self.menu.cancelled or (choice is not None and choice.close):
            self.finish()
        else:
            self.view.setNeedsDisplay_(True)

    def finish(self) -> None:
        if self.finished:  # hiding the panel makes it resign key, which calls us again
            return
        self.finished = True
        self.panel.orderOut_(None)
        _stop_event_loop(self.app)


# --------------------------------------------------------------------------- AppKit classes


class _Panel(NSPanel):
    """A borderless panel that can take keyboard focus, and cancels the menu if it loses it."""

    def canBecomeKeyWindow(self):
        return True

    def resignKeyWindow(self):
        objc.super(_Panel, self).resignKeyWindow()
        # The user clicked somewhere else: a launcher that lingers unfocused is worse than none.
        if (session := getattr(self, "session", None)) is not None:
            session.finish()


class _InputView(MenuView):
    """The menu view, plus keyboard input: it is the panel's first responder, so key events land here."""

    def acceptsFirstResponder(self):
        return True

    def keyDown_(self, event):
        self.session.on_key(event)


class _Delegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.session.show()


def _make_panel(rect: Rect, session: _Session) -> NSPanel:
    panel = _Panel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(*rect), NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False
    )
    panel.session = session
    panel.setLevel_(NSStatusWindowLevel)  # above normal windows, and above the menu bar
    panel.setHasShadow_(False)
    panel.setReleasedWhenClosed_(False)
    panel.setCollectionBehavior_(  # appear on whichever Space is current, even over a fullscreen app
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorIgnoresCycle
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    panel.setContentView_(session.view)
    return panel


# --------------------------------------------------------------------------- small helpers


def menu_rect(screen: Rect, height: float, topbar: bool) -> Rect:
    """Where the menu goes: the full width of the screen, flush with its top or bottom edge.

    `screen` is in AppKit coordinates, where y grows UP, so "the top" is the larger y.
    """
    x, y, width, screen_height = screen
    return (x, y + screen_height - height if topbar else y, width, height)


def pick_screen(monitor: int) -> NSScreen:
    """`-m N` if given, otherwise the screen the mouse pointer is on, otherwise the main screen."""
    screens = NSScreen.screens()
    if 0 <= monitor < len(screens):
        return screens[monitor]
    mouse = NSEvent.mouseLocation()
    for screen in screens:
        f = screen.frame()
        inside_x = f.origin.x <= mouse.x < f.origin.x + f.size.width
        inside_y = f.origin.y <= mouse.y < f.origin.y + f.size.height
        if inside_x and inside_y:
            return screen
    return NSScreen.mainScreen()


def fit_per_page(menu: Menu, settings: Settings, style: Style, width: float) -> int:
    """How many items fit in a horizontal menu.

    dmenu re-measures the items to find where each page ends, so its pages hold different numbers
    of items. `Menu` has one fixed page size instead, which is simpler to reason about, so we size
    the page by the widest items: it can show fewer items than strictly fit, never too many.
    """
    prompt = cell_width(style, settings.prompt) if settings.prompt else 0
    room = width - prompt - width / 3 - cell_width(style, "<") - cell_width(style, ">")
    longest = heapq.nlargest(50, menu.items, key=len)  # measuring every item would be slow for big lists
    widest = max((cell_width(style, item) for item in longest), default=1)
    return max(1, int(room // widest))


def read_clipboard() -> str:
    return str(NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString) or "")


def _stop_event_loop(app: NSApplication) -> None:
    """End `app.run()`. `stop_` is only noticed when the loop next handles an event, so post one."""
    app.stop_(None)
    make_event = (
        NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_
    )
    app.postEvent_atStart_(make_event(NSEventTypeApplicationDefined, (0, 0), 0, 0, 0, None, 0, 0, 0), True)
