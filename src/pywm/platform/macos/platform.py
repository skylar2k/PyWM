"""`MacOSPlatform`: the `Platform` protocol implemented with AX, CoreGraphics and AppKit."""

import contextlib
import logging
import subprocess
import threading
import time
from collections.abc import Callable
from signal import SIGHUP, SIGTERM
from types import ModuleType
from typing import Any

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSRunningApplication,
)
from PyObjCTools import AppHelper, MachSignals
from Quartz import CGWindowListCopyWindowInfo, kCGNullWindowID, kCGWindowListOptionAll, kCGWindowNumber

from pywm.core.keys import Chord
from pywm.core.types import Screen, WindowId, WindowInfo
from pywm.geometry import Rect
from pywm.platform.events import Event, WindowsChanged
from pywm.platform.macos import ax
from pywm.platform.macos.hotkeys import HotkeyTap
from pywm.platform.macos.observers import AppObserver
from pywm.platform.macos.parking import Parking, corner
from pywm.platform.macos.screens import read_screens
from pywm.platform.macos.workspace import OWN_PID, WorkspaceWatcher, running_pids

log = logging.getLogger(__name__)

BACKOFF = 2.0  # seconds to leave an unresponsive app alone


class MacOSPlatform:
    def __init__(self, config: ModuleType) -> None:
        self.config = config
        ax.set_global_timeout(config.AX_TIMEOUT)
        self._on_event: Callable[[Event], None] = lambda e: None
        self._observers: dict[int, AppObserver] = {}
        self._elements: dict[WindowId, Any] = {}  # window id -> AXUIElement
        self._pid_of: dict[WindowId, int] = {}
        self._parking = Parking()
        self._screens: list[Screen] = []
        self._backoff_until: dict[int, float] = {}
        self._tap: HotkeyTap | None = None
        self._workspace: WorkspaceWatcher | None = None
        self._cg_cache: tuple[float, set[int]] = (0.0, set())

    # ------------------------------------------------------------------ reading

    def screens(self) -> list[Screen]:
        self._screens = read_screens()
        return self._screens

    def app_pids(self) -> list[int]:
        return running_pids()

    def window_infos(self, pid: int) -> list[WindowInfo] | None:
        if self._backing_off(pid):
            return None
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is None:
            return []
        observer = self._observer_for(pid)
        try:
            elements = ax.get(observer.element, "AXWindows") or []
            infos = []
            for el in elements:
                if (info := self._read_window(pid, app, el)) is None:
                    continue
                self._elements[info.id], self._pid_of[info.id] = el, pid
                observer.watch(info.id, el)
                infos.append(info)
        except ax.AXUnresponsive:
            self._back_off(pid)
            return None
        except ax.AXFailure as e:
            log.debug("cannot list windows of pid %d: %s", pid, e)
            return None
        live = {i.id for i in infos}
        for wid in [w for w, p in self._pid_of.items() if p == pid and w not in live]:
            self._elements.pop(wid, None)
            self._pid_of.pop(wid, None)
            observer.forget(wid)
        return infos

    def _read_window(self, pid: int, app: Any, el: Any) -> WindowInfo | None:
        wid = ax.window_id(el)
        frame = ax.frame(el)
        if wid is None or frame is None:
            return None
        return WindowInfo(
            id=wid,
            pid=pid,
            app=str(app.localizedName() or ""),
            bundle_id=str(app.bundleIdentifier() or ""),
            title=str(ax.get(el, "AXTitle") or ""),
            subrole=(str(s) if (s := ax.get(el, "AXSubrole")) else None),
            frame=self._parking.frames.get(wid, frame),  # a parked window reports where it *lives*
            minimized=bool(ax.get(el, "AXMinimized")),
            fullscreen=bool(ax.get(el, ax.FULLSCREEN)),
            resizable=ax.is_settable(el, "AXSize"),
            away=bool(app.isHidden()),
        )

    def window_exists(self, wid: WindowId) -> bool:
        """Is this window alive somewhere, even on a Space AX cannot see into?

        AX only lists windows on the *current* Space. CoreGraphics lists all of
        them, so it can tell "moved to another Space" apart from "closed".
        """
        now = time.monotonic()
        stamp, ids = self._cg_cache
        if now - stamp > 0.25:
            listing = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID) or []
            ids = {int(w[kCGWindowNumber]) for w in listing}
            self._cg_cache = (now, ids)
        return wid in ids

    def focused_window(self) -> WindowId | None:
        try:
            app = ax.get(ax.system_wide(), "AXFocusedApplication")
            if app is None or ax.pid_of(app) == OWN_PID:
                return None
            el = ax.get(app, "AXFocusedWindow")
            return ax.window_id(el) if el is not None else None
        except ax.AXFailure:
            return None

    # ------------------------------------------------------------------ writing

    def set_frame(self, wid: WindowId, rect: Rect) -> Rect | None:
        el, pid = self._elements.get(wid), self._pid_of.get(wid)
        if el is None or pid is None or self._backing_off(pid):
            return None
        try:
            self._parking.unpark(wid)
            # Size, position, size: when a window moves to a different display the first
            # resize can be clamped by the old one, and the second corrects it.
            ax.set_size(el, rect.w, rect.h)
            ax.set_position(el, rect.x, rect.y)
            ax.set_size(el, rect.w, rect.h)
            return ax.frame(el)  # read back what the app actually did
        except ax.AXUnresponsive:
            self._back_off(pid)
        except ax.AXFailure as e:
            log.debug("set_frame(%d) failed: %s", wid, e)
        return None

    def hide(self, wid: WindowId) -> None:
        el, pid = self._elements.get(wid), self._pid_of.get(wid)
        if el is None or pid is None or wid in self._parking or self._backing_off(pid):
            return
        try:
            if (frame := ax.frame(el)) is None:
                return
            self._parking.park(wid, frame)
            ax.set_position(el, *corner(self._screens or self.screens()))
        except ax.AXUnresponsive:
            self._back_off(pid)
        except ax.AXFailure as e:
            log.debug("hide(%d) failed: %s", wid, e)

    def show(self, wid: WindowId) -> None:
        el, pid = self._elements.get(wid), self._pid_of.get(wid)
        if wid not in self._parking:
            return
        frame = self._parking.unpark(wid)
        if el is None or pid is None or frame is None:
            return
        try:
            ax.set_position(el, frame.x, frame.y)
        except ax.AXFailure:
            self._back_off(pid)

    def focus(self, wid: WindowId) -> None:
        """Make a window the focused one. Plain AX, so it works from a background process.

        (`NSRunningApplication.activate()` is deliberately not used: since macOS 14 an
        app may only be activated by the *frontmost* app unless it yields.)
        """
        el, pid = self._elements.get(wid), self._pid_of.get(wid)
        if el is None or pid is None or self._backing_off(pid):
            return
        try:
            app = self._observer_for(pid).element
            ax.set_(app, "AXFrontmost", True)
            ax.set_(el, "AXMain", True)
            ax.set_(app, "AXFocusedWindow", el)
            ax.perform(el, "AXRaise")
        except ax.AXUnresponsive:
            self._back_off(pid)
        except ax.AXFailure as e:
            log.debug("focus(%d) failed: %s", wid, e)

    def raise_window(self, wid: WindowId) -> None:
        el, pid = self._elements.get(wid), self._pid_of.get(wid)
        if el is None or pid is None or self._backing_off(pid):
            return
        with contextlib.suppress(ax.AXFailure):
            ax.perform(el, "AXRaise")

    def close(self, wid: WindowId) -> None:
        """Press the window's close button, which is what a click would do (and asks to save)."""
        el, pid = self._elements.get(wid), self._pid_of.get(wid)
        if el is None or pid is None:
            return
        try:
            if (button := ax.get(el, "AXCloseButton")) is not None:
                ax.perform(button, "AXPress")
        except ax.AXFailure as e:
            log.debug("close(%d) failed: %s", wid, e)

    def spawn(self, argv: tuple[str, ...]) -> None:
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as e:
            log.error("cannot run %s: %s", argv, e)
            return
        threading.Thread(target=proc.wait, daemon=True).start()  # reap it so no zombie remains

    def restore_all(self) -> None:
        for wid in list(self._parking.frames):
            self.show(wid)

    # ------------------------------------------------------------------ plumbing

    def grab_keys(self, chords: set[Chord], on_chord: Callable[[Chord], None]) -> None:
        self._tap = HotkeyTap(chords, on_chord)
        if not self._tap.start():
            log.error(
                "running WITHOUT hotkeys: grant Accessibility and Input Monitoring to your terminal app"
            )

    def call_later(self, delay: float, fn: Callable[[], None]) -> None:
        AppHelper.callLater(delay, fn)

    def run(self, on_event: Callable[[Event], None]) -> None:
        self._on_event = on_event
        # An NSApplication, even one that never "runs", makes AppKit behave: notifications
        # are delivered and our status-bar windows can be drawn. "Accessory" means no Dock icon.
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        self._workspace = WorkspaceWatcher(self._emit)
        self._workspace.start()
        for pid in self.app_pids():
            self._observer_for(pid)
        for sig in (SIGTERM, SIGHUP):
            MachSignals.signal(sig, lambda _: AppHelper.stopEventLoop())
        AppHelper.runEventLoop(installInterrupt=True)

    def stop(self) -> None:
        AppHelper.stopEventLoop()

    # ------------------------------------------------------------------ internals

    def _emit(self, event: Event) -> None:
        self._on_event(event)

    def _observer_for(self, pid: int) -> AppObserver:
        obs = self._observers.get(pid)
        if obs is None or not obs.active:
            if obs is not None:
                obs.close()
            obs = AppObserver(pid, ax.application(pid, self.config.AX_TIMEOUT), self._emit)
            self._observers[pid] = obs
        return obs

    def _backing_off(self, pid: int) -> bool:
        return self._backoff_until.get(pid, 0.0) > time.monotonic()

    def _back_off(self, pid: int) -> None:
        """An app stopped answering. Leave it alone for a bit, then look again."""
        log.warning("pid %d is not responding; ignoring it for %.0fs", pid, BACKOFF)
        self._backoff_until[pid] = time.monotonic() + BACKOFF
        AppHelper.callLater(BACKOFF + 0.1, lambda: self._emit(WindowsChanged(pid)))
