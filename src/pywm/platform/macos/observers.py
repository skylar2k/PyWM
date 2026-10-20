"""One `AXObserver` per running app: macOS tells us when windows come and go.

Which notification goes on which element is the fiddly part:

    on the *application* element           on each *window* element
    ------------------------------------   ------------------------------------
    kAXWindowCreatedNotification           kAXUIElementDestroyedNotification
    kAXFocusedWindowChangedNotification    kAXWindowMiniaturizedNotification
                                           kAXWindowDeminiaturizedNotification

"Destroyed" is delivered *by the dying element*, so it can only be heard if we
subscribed on that window beforehand. That is why `watch()` is called for every
window we see.

The callback does not try to be clever: it just says "something about app X
changed". The controller then re-reads the app's windows and diffs.
"""

import logging
from collections.abc import Callable
from typing import Any

import objc
from ApplicationServices import (
    AXObserverAddNotification,
    AXObserverCreate,
    AXObserverGetRunLoopSource,
    AXObserverRemoveNotification,
    kAXErrorNotificationAlreadyRegistered,
    kAXErrorSuccess,
    kAXFocusedWindowChangedNotification,
    kAXUIElementDestroyedNotification,
    kAXWindowCreatedNotification,
    kAXWindowDeminiaturizedNotification,
    kAXWindowMiniaturizedNotification,
)
from CoreFoundation import (
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRemoveSource,
    kCFRunLoopCommonModes,
)

from pywm.platform.events import Event, FocusChanged, WindowsChanged

log = logging.getLogger(__name__)

APP_NOTIFICATIONS = (kAXWindowCreatedNotification, kAXFocusedWindowChangedNotification)
WINDOW_NOTIFICATIONS = (
    kAXUIElementDestroyedNotification,
    kAXWindowMiniaturizedNotification,
    kAXWindowDeminiaturizedNotification,
)


class AppObserver:
    def __init__(self, pid: int, app_element: Any, emit: Callable[[Event], None]) -> None:
        self.pid = pid
        self.element = app_element
        self._watched: set[int] = set()
        self._observer = None
        self._source = None

        # The callback must stay referenced for as long as the observer lives,
        # otherwise PyObjC may free the C trampoline underneath macOS.
        @objc.callbackFor(AXObserverCreate)
        def callback(observer, element, notification, refcon):
            if str(notification) == kAXFocusedWindowChangedNotification:
                emit(FocusChanged())
            else:
                emit(WindowsChanged(pid))

        self._callback = callback
        err, observer = AXObserverCreate(pid, callback, None)
        if err != kAXErrorSuccess or observer is None:
            log.debug("cannot observe pid %d (AX error %s)", pid, err)
            return
        self._observer = observer
        for note in APP_NOTIFICATIONS:
            self._add(app_element, note)
        self._source = AXObserverGetRunLoopSource(observer)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), self._source, kCFRunLoopCommonModes)

    @property
    def active(self) -> bool:
        return self._observer is not None

    def _add(self, element: Any, notification: str) -> bool:
        err = AXObserverAddNotification(self._observer, element, notification, None)
        return err in (kAXErrorSuccess, kAXErrorNotificationAlreadyRegistered)

    def watch(self, window_id: int, element: Any) -> None:
        """Subscribe to one window's notifications (idempotent)."""
        if self._observer is None or window_id in self._watched:
            return
        if all([self._add(element, note) for note in WINDOW_NOTIFICATIONS]):
            self._watched.add(window_id)

    def forget(self, window_id: int) -> None:
        self._watched.discard(window_id)

    def close(self) -> None:
        if self._source is not None:
            CFRunLoopRemoveSource(CFRunLoopGetCurrent(), self._source, kCFRunLoopCommonModes)
        if self._observer is not None:
            for note in APP_NOTIFICATIONS:
                AXObserverRemoveNotification(self._observer, self.element, note)
        self._observer = self._source = None
