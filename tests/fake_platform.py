"""An in-memory Platform: lets the controller run in tests with no screen.

It even models the awkward parts of macOS (windows with a minimum size) so the
size-learning logic can be exercised without a real display.
"""

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

from pywm.core.keys import Chord
from pywm.core.types import Screen, WindowId, WindowInfo
from pywm.geometry import Rect
from pywm.platform.events import Event

OFFSCREEN = 100_000


@dataclass(slots=True)
class FakeWindow:
    id: WindowId
    pid: int
    app: str
    title: str
    frame: Rect
    subrole: str = "AXStandardWindow"
    min_size: tuple[int, int] = (0, 0)
    saved_frame: Rect | None = None  # set while hidden


@dataclass
class FakePlatform:  # no slots: tests may monkeypatch methods
    screen_list: list[Screen] = field(
        default_factory=lambda: [Screen(1, "Fake Display", Rect(0, 0, 1600, 1000), Rect(0, 25, 1600, 975))]
    )
    windows: dict[WindowId, FakeWindow] = field(default_factory=dict)
    focused: WindowId | None = None
    log: list[tuple] = field(default_factory=list)
    timers: list[tuple[float, Callable[[], None]]] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(100))
    grabbed: set[Chord] = field(default_factory=set)

    # --- test helpers -------------------------------------------------------------

    def add_window(self, app: str = "App", title: str = "", pid: int | None = None, **kw: object) -> WindowId:
        wid = next(self._ids)
        self.windows[wid] = FakeWindow(
            wid,
            pid or wid,
            app,
            title or f"{app} {wid}",
            Rect(300, 200, 800, 600),
            **kw,  # type: ignore[arg-type]
        )
        return wid

    def remove_window(self, wid: WindowId) -> None:
        self.windows.pop(wid, None)
        if self.focused == wid:
            self.focused = None

    def run_timers(self) -> None:
        """Fire everything scheduled with call_later, in order of delay."""
        while self.timers:
            self.timers.sort(key=lambda t: t[0])
            _, fn = self.timers.pop(0)
            fn()

    def visible_frames(self) -> dict[WindowId, Rect]:
        return {w.id: w.frame for w in self.windows.values() if w.saved_frame is None}

    # --- Platform protocol --------------------------------------------------------

    def screens(self) -> list[Screen]:
        return list(self.screen_list)

    def app_pids(self) -> list[int]:
        return sorted({w.pid for w in self.windows.values()})

    def window_infos(self, pid: int) -> list[WindowInfo] | None:
        return [
            WindowInfo(w.id, w.pid, w.app, f"fake.{w.app.lower()}", w.title, w.subrole, w.frame)
            for w in self.windows.values()
            if w.pid == pid
        ]

    def window_exists(self, wid: WindowId) -> bool:
        return wid in self.windows

    def focused_window(self) -> WindowId | None:
        return self.focused

    def set_frame(self, wid: WindowId, rect: Rect) -> Rect | None:
        w = self.windows.get(wid)
        if w is None:
            return None
        self.log.append(("set_frame", wid, rect))
        w.saved_frame = None
        w.frame = Rect(rect.x, rect.y, max(rect.w, w.min_size[0]), max(rect.h, w.min_size[1]))
        return w.frame

    def hide(self, wid: WindowId) -> None:
        if (w := self.windows.get(wid)) and w.saved_frame is None:
            self.log.append(("hide", wid))
            w.saved_frame, w.frame = w.frame, Rect(OFFSCREEN, OFFSCREEN, w.frame.w, w.frame.h)

    def show(self, wid: WindowId) -> None:
        if (w := self.windows.get(wid)) and w.saved_frame is not None:
            self.log.append(("show", wid))
            w.frame, w.saved_frame = w.saved_frame, None

    def focus(self, wid: WindowId) -> None:
        self.log.append(("focus", wid))
        self.focused = wid

    def raise_window(self, wid: WindowId) -> None:
        self.log.append(("raise", wid))

    def close(self, wid: WindowId) -> None:
        self.log.append(("close", wid))
        self.remove_window(wid)

    def spawn(self, argv: tuple[str, ...]) -> None:
        self.log.append(("spawn", argv))

    def restore_all(self) -> None:
        for wid in list(self.windows):
            self.show(wid)

    def grab_keys(self, chords: set[Chord], on_chord: Callable[[Chord], None]) -> None:
        self.grabbed = chords

    def call_later(self, delay: float, fn: Callable[[], None]) -> None:
        self.timers.append((delay, fn))

    def run(self, on_event: Callable[[Event], None]) -> None:
        pass  # tests drive the controller directly

    def stop(self) -> None:
        self.log.append(("stop",))
