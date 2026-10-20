"""NSWorkspace notifications: which apps start, quit, hide, and which Space is active.

AX observers are per-app, so something has to tell us when an app appears. That
is NSWorkspace's job. These are plain block-based observers; no NSObject subclass needed.
"""

import os
from collections.abc import Callable
from typing import Any

from AppKit import (
    NSApplicationActivationPolicyRegular,
    NSApplicationDidChangeScreenParametersNotification,
    NSWorkspace,
    NSWorkspaceActiveSpaceDidChangeNotification,
    NSWorkspaceDidActivateApplicationNotification,
    NSWorkspaceDidHideApplicationNotification,
    NSWorkspaceDidLaunchApplicationNotification,
    NSWorkspaceDidTerminateApplicationNotification,
    NSWorkspaceDidUnhideApplicationNotification,
)
from Foundation import NSNotificationCenter
from Quartz import CGDisplayRegisterReconfigurationCallback, kCGDisplayBeginConfigurationFlag

from pywm.platform.events import (
    AppLaunched,
    AppTerminated,
    Event,
    FocusChanged,
    ScreensChanged,
    WindowsChanged,
)

OWN_PID = os.getpid()


def is_manageable(app: Any) -> bool:
    """Regular apps (the kind with a Dock icon and windows). Not us, not menu-bar helpers."""
    return (
        app.activationPolicy() == NSApplicationActivationPolicyRegular and app.processIdentifier() != OWN_PID
    )


def running_pids() -> list[int]:
    return [
        int(a.processIdentifier())
        for a in NSWorkspace.sharedWorkspace().runningApplications()
        if is_manageable(a)
    ]


class WorkspaceWatcher:
    def __init__(self, emit: Callable[[Event], None]) -> None:
        self._emit = emit
        self._tokens: list[Any] = []  # observers vanish if their token is released

    def start(self) -> None:
        center = NSWorkspace.sharedWorkspace().notificationCenter()

        def app_of(note: Any) -> Any | None:
            app = note.userInfo().get("NSWorkspaceApplicationKey")
            return app if app is not None and is_manageable(app) else None

        def on(name: str, make: Callable[[Any], Event | None]) -> None:
            def handler(note: Any) -> None:
                if (event := make(note)) is not None:
                    self._emit(event)

            self._tokens.append(center.addObserverForName_object_queue_usingBlock_(name, None, None, handler))

        def with_app(factory: Callable[[int], Event]) -> Callable[[Any], Event | None]:
            return lambda note: factory(int(app.processIdentifier())) if (app := app_of(note)) else None

        on(NSWorkspaceDidLaunchApplicationNotification, with_app(AppLaunched))
        on(NSWorkspaceDidTerminateApplicationNotification, with_app(AppTerminated))
        on(NSWorkspaceDidHideApplicationNotification, with_app(WindowsChanged))
        on(NSWorkspaceDidUnhideApplicationNotification, with_app(WindowsChanged))
        on(NSWorkspaceDidActivateApplicationNotification, lambda note: FocusChanged())
        # Entering/leaving native fullscreen, or Mission Control, changes the active Space.
        on(NSWorkspaceActiveSpaceDidChangeNotification, lambda note: ScreensChanged())

        # Displays plugged, unplugged or rearranged. CoreGraphics calls back twice per change
        # (once "about to begin", once when done); we only care about the second.
        def display_changed(display, flags, user_info):
            if not flags & kCGDisplayBeginConfigurationFlag:
                self._emit(ScreensChanged())

        self._display_callback = display_changed
        CGDisplayRegisterReconfigurationCallback(display_changed, None)

        # Dock resized/auto-hidden, menu bar toggled: the *usable* area changed. AppKit posts this
        # on the default center (which works because `MacOSPlatform.run` created an NSApplication).
        self._tokens.append(
            NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                NSApplicationDidChangeScreenParametersNotification,
                None,
                None,
                lambda note: self._emit(ScreensChanged()),
            )
        )
