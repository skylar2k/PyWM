"""The imperative shell: wires a Platform to the WindowManager.

    OS event ──► Controller ──► WindowManager (pure) ──► Plan ──► Controller ──► OS

The shell has all the messy, stateful, failure-prone work: debouncing, retrying,
reading back what apps really did. Keeping it separate means the WM itself can
stay simple enough to test with plain asserts.
"""

import logging
from collections.abc import Callable
from typing import Any

from pywm.core.keys import Chord, Key
from pywm.core.types import Close, Hide, Placement, Plan, Quit, Show, Spawn, WindowId
from pywm.core.wm import WindowManager
from pywm.platform import Platform
from pywm.platform.events import (
    AppLaunched,
    AppTerminated,
    Event,
    FocusChanged,
    ScreensChanged,
    WindowsChanged,
    WindowsMoved,
)

log = logging.getLogger(__name__)

DEBOUNCE = 0.03  # seconds to let a burst of notifications settle before re-reading
LAUNCH_RETRIES = (0.15, 0.5, 1.5)  # new apps are often not ready for AX calls right away


class Controller:
    def __init__(self, platform: Platform, wm: WindowManager, keys: list[Key]) -> None:
        self.platform, self.wm = platform, wm
        self._bound = {k.chord: k for k in keys}  # if a chord is bound twice, the last one wins
        self._applied: dict[WindowId, Placement] = {}  # what we last told the OS, per window
        self._pending: set[int] = set()  # pids with a debounced re-sync queued
        self._stopping = False

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        self.refresh_screens()
        for pid in self.platform.app_pids():
            self.resync(pid)
        self.wm.window_focused(self.platform.focused_window())
        self.apply()
        self.platform.grab_keys(set(self._bound), self.on_chord)
        log.info("managing %d windows on %d monitor(s)", len(self.wm.windows), len(self.wm.monitors))
        self.platform.run(self.handle)

    def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.platform.restore_all()
        self.platform.stop()

    # ------------------------------------------------------------------ inputs

    def handle(self, event: Event) -> None:
        match event:
            case AppLaunched(pid):
                self.resync_soon(pid)
                for delay in LAUNCH_RETRIES:
                    self.platform.call_later(delay, lambda pid=pid: self.resync(pid, apply=True))
            case AppTerminated(pid):
                self.wm.remove_app(pid)
                self.apply()
            case WindowsChanged(pid):
                self.resync_soon(pid)
            case WindowsMoved(pid):
                ...
            case FocusChanged():
                self.wm.window_focused(self.platform.focused_window())
                self.apply()
            case ScreensChanged():
                self.refresh_screens()
                self.apply()
                for pid in self.platform.app_pids():
                    self.resync_soon(pid)

    def on_chord(self, chord: Chord) -> None:
        key = self._bound[chord]
        log.debug("%r", key)
        self.execute(key.action, *key.args)

    def execute(self, action: Callable[..., None], *args: Any) -> None:
        """Run `action(wm, *args)` and apply the result. A buggy action is logged, never fatal."""
        try:
            action(self.wm, *args)
        except Exception:
            log.exception("%s failed", getattr(action, "__qualname__", action))
        self.apply()

    # ------------------------------------------------------------------ syncing

    def refresh_screens(self) -> None:
        screens = self.platform.screens()
        current = [(m.id, m.frame, m.work_area) for m in self.wm.monitors]
        if [
            (s.id, s.frame, s.work_area) for s in sorted(screens, key=lambda s: (s.frame.x, s.frame.y))
        ] != current:
            self.wm.set_screens(screens)

    def resync_soon(self, pid: int) -> None:
        """Queue one re-sync of `pid`; bursts of notifications collapse into a single one."""
        if pid in self._pending:
            return
        self._pending.add(pid)

        def run() -> None:
            self._pending.discard(pid)
            self.resync(pid, apply=True)

        self.platform.call_later(DEBOUNCE, run)

    def resync(self, pid: int, apply: bool = False) -> None:
        infos = self.platform.window_infos(pid)
        if infos is None:  # app is hung or gone: keep what we know rather than forgetting it
            return
        self.wm.sync_app(pid, infos, exists=self.platform.window_exists)
        self.wm.window_focused(self.platform.focused_window())
        if apply:
            self.apply()

    # ------------------------------------------------------------------ output

    def apply(self) -> None:
        """Make the OS match the model. Two passes at most: the second one absorbs
        what the first one taught us about windows that refused to resize."""
        for _ in range(2):
            plan = self.wm.flush()
            if not self._execute(plan):
                break
        for gone in self._applied.keys() - self.wm.windows.keys():
            del self._applied[gone]

    def _execute(self, plan: Plan) -> bool:
        """Carry out a plan. Returns True if we learned something and should re-plan."""
        relearned = changed = False
        for wid, placement in plan.placements.items():
            if self._applied.get(wid) == placement:
                continue
            changed = True
            match placement:
                case Hide():
                    self.platform.hide(wid)
                case Show(rect=None):
                    self.platform.show(wid)
                case Show(rect=rect):
                    actual = self.platform.set_frame(wid, rect)
                    if actual is None:
                        continue  # failed (hung app?); leave it unrecorded so we retry later
                    if not actual.close_to(rect) and self.wm.learn_size(wid, rect, actual):
                        relearned = True
            self._applied[wid] = placement
        if changed:
            for wid in plan.raise_order:
                self.platform.raise_window(wid)
        if plan.focus is not None:
            self.platform.focus(plan.focus)
        for action in plan.actions:
            match action:
                case Close(wid):
                    self.platform.close(wid)
                case Spawn(argv):
                    self.platform.spawn(argv)
                case Quit():
                    self.stop()
        return relearned
