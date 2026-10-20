"""The window manager's brain: a state machine with no I/O.

Inputs are method calls (OS events, user commands). The output is a `Plan` that
`flush()` computes from the current state. Nothing in this file touches macOS,
which is why the whole thing is unit-testable on any machine. This split is
usually called "functional core, imperative shell"; the shell is `controller.py`.

The data model is a direct translation of dwm's:

    dwm (C)                 pywm
    ----------------------  -----------------------------------------
    Client                  Window          (core/types.py)
    Monitor                 Monitor         (core/monitor.py)
    Monitor.clients         Monitor.order   tiling order, [0] is master
    Monitor.stack           Monitor.stack   focus history, [0] is latest
    Client.tags (bitmask)   Window.tags
    rules[]                 config.RULES
    arrange()               WindowManager.flush()
"""

from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType

from pywm.core.events import Signal
from pywm.core.layouts import LAYOUTS, arrange, fit
from pywm.core.monitor import Monitor, TagSettings
from pywm.core.rules import first_match
from pywm.core.types import (
    UNBOUNDED,
    Action,
    Close,
    Hide,
    Placement,
    Plan,
    Quit,
    Role,
    Screen,
    Show,
    Spawn,
    Window,
    WindowId,
    WindowInfo,
    classify,
)
from pywm.geometry import Rect


@dataclass(frozen=True, slots=True)
class MonitorStatus:
    """What a status bar needs to know about one monitor. Immutable on purpose."""

    monitor: int
    current: bool  # is this the monitor that has focus?
    tag_names: tuple[str, ...]
    occupied: int  # bitmask of tags that have windows
    selected: int  # bitmask of tags being viewed
    layout_symbol: str
    title: str
    bar_rect: Rect | None


class WindowManager:
    def __init__(self, config: ModuleType) -> None:
        """`config` is the `pywm.config` module (or anything with the same UPPERCASE names)."""
        self.config = config
        self.windows: dict[WindowId, Window] = {}
        self.monitors: list[Monitor] = []
        self.selmon = 0  # index into self.monitors
        self.changed: Signal[[list[MonitorStatus]]] = Signal()
        self._focus_request: WindowId | None = None
        self._actions: list[Action] = []

    # ------------------------------------------------------------------ queries

    @property
    def cur(self) -> Monitor:
        return self.monitors[self.selmon]

    def monitor_of(self, w: Window) -> Monitor:
        return next(m for m in self.monitors if m.id == w.monitor)

    def visible(self, mon: Monitor) -> list[Window]:
        """Windows shown on `mon` right now, in tiling order."""
        ws = (self.windows[i] for i in mon.order)
        return [w for w in ws if not w.suspended and w.tags & mon.tagset]

    def selected(self, mon: Monitor | None = None) -> Window | None:
        """The window that has (or should have) focus on a monitor."""
        mon = mon or self.cur
        visible = {w.id for w in self.visible(mon)}
        return next((self.windows[i] for i in mon.stack if i in visible), None)

    # ------------------------------------------------------------------ screens

    def set_screens(self, screens: list[Screen]) -> None:
        """(Re)build the monitor list. Monitors that persist keep their tags and layouts."""
        cfg = self.config
        defaults = TagSettings(cfg.NMASTER, cfg.MFACT, cfg.LAYOUT, "float")
        old = {m.id: m for m in self.monitors}
        current_id = self.cur.id if self.monitors else None
        monitors: list[Monitor] = []
        for s in sorted(screens, key=lambda s: (s.frame.x, s.frame.y)):
            if s.id in old:
                m = old.pop(s.id)
                m.name, m.frame, m.work_area = s.name, s.frame, s.work_area
            else:
                m = Monitor(
                    s.id,
                    s.name,
                    s.frame,
                    s.work_area,
                    ntags=len(cfg.TAGS),
                    default_settings=defaults,
                    show_bar=cfg.BAR_ENABLED,
                )
            monitors.append(m)
        if not monitors:
            return
        # Windows on unplugged monitors move to the first remaining one.
        for gone in old.values():
            first = monitors[0]
            for wid in gone.order:
                w = self.windows[wid]
                w.monitor, w.tags = first.id, first.tagset
                first.order.append(wid)
                first.stack.append(wid)
        self.monitors = monitors
        self.selmon = next((i for i, m in enumerate(monitors) if m.id == current_id), 0)

    # ------------------------------------------------------------------ OS events

    def sync_app(
        self, pid: int, infos: list[WindowInfo], exists: Callable[[WindowId], bool] = lambda _: False
    ) -> None:
        """Make the model of one app's windows match a fresh snapshot.

        OS notifications are only *hints* that something changed; we never trust
        them to say what. Instead we diff snapshot against model. That is
        level-triggered rather than edge-triggered, and it makes missed or
        duplicated notifications harmless.

        `exists(id)` says whether a window we know about but which is missing
        from the snapshot is still alive somewhere (another Space), as opposed
        to really closed.
        """
        seen: set[WindowId] = set()
        for info in infos:
            if (w := self.windows.get(info.id)) is not None:
                if classify(info.subrole) is Role.IGNORED:
                    continue  # leave it unseen so it is removed below
                self._update(w, info)
                seen.add(info.id)
            elif self._adopt(info):
                seen.add(info.id)
        for w in [w for w in self.windows.values() if w.pid == pid and w.id not in seen]:
            if exists(w.id):
                w.away = True
            else:
                self.remove_window(w.id)

    def remove_app(self, pid: int) -> None:
        for w in [w for w in self.windows.values() if w.pid == pid]:
            self.remove_window(w.id)

    def _adopt(self, info: WindowInfo) -> bool:
        role = classify(info.subrole)
        rule = first_match(self.config.RULES, info)
        if role is Role.IGNORED or (rule and rule.ignore) or not self.monitors:
            return False
        mon = self._monitor_for(info.frame)
        if rule and rule.monitor is not None and rule.monitor < len(self.monitors):
            mon = self.monitors[rule.monitor]
        tags = mon.tagset
        if rule and rule.tag and 1 <= rule.tag <= mon.ntags:
            tags = 1 << (rule.tag - 1)
        floating = role is Role.FLOATING or not info.resizable
        if rule and rule.floating is not None:
            floating = rule.floating or role is Role.FLOATING
        w = Window(
            info.id,
            info.pid,
            info.app,
            info.bundle_id,
            info.title,
            info.frame,
            tags,
            mon.id,
            floating,
            minimized=info.minimized,
            fullscreen=info.fullscreen,
            away=info.away,
        )
        self.windows[w.id] = w
        if self.config.NEW_AT_MASTER:
            mon.order.insert(0, w.id)
        else:
            mon.order.append(w.id)
        mon.stack.insert(0, w.id)
        return True

    def _update(self, w: Window, info: WindowInfo) -> None:
        w.title, w.frame = info.title, info.frame
        w.minimized, w.fullscreen, w.away = info.minimized, info.fullscreen, info.away

    def _monitor_for(self, frame: Rect) -> Monitor:
        best = max(self.monitors, key=lambda m: frame.overlap_area(m.frame))
        return best if frame.overlap_area(best.frame) else self.cur

    def remove_window(self, wid: WindowId) -> None:
        w = self.windows.get(wid)
        if w is None:
            return
        mon = self.monitor_of(w)
        was_selected = self.selected(mon) is w
        del self.windows[wid]
        mon.order.remove(wid)
        mon.stack.remove(wid)
        if was_selected and mon is self.cur:
            self.focus(None)  # like dwm's unmanage(): hand focus to the next window

    def window_focused(self, wid: WindowId | None) -> None:
        """The OS says focus moved. Record it; do not fight it."""
        w = self.windows.get(wid) if wid is not None else None
        if w is None or w.suspended:
            return
        mon = self.monitor_of(w)
        if not w.tags & mon.tagset and self.config.FOLLOW_FOCUS:
            mon.view(w.tags)  # e.g. Cmd-Tab to an app whose window is on another tag
        if w.tags & mon.tagset:
            self.selmon = self.monitors.index(mon)
            mon.stack.remove(w.id)
            mon.stack.insert(0, w.id)

    def learn_size(self, wid: WindowId, requested: Rect, actual: Rect) -> bool:
        """Remember limits an app revealed by not doing what it was told.

        Returns True if that is news, meaning the layout should be recomputed.
        """
        w = self.windows.get(wid)
        if w is None:
            return False
        before = (w.min_size, w.max_size)
        min_w, min_h = w.min_size or (0, 0)
        max_w, max_h = w.max_size or (UNBOUNDED, UNBOUNDED)
        if actual.w > requested.w + 1:
            min_w = actual.w
        elif actual.w < requested.w - 1:
            max_w = actual.w
        if actual.h > requested.h + 1:
            min_h = actual.h
        elif actual.h < requested.h - 1:
            max_h = actual.h
        w.min_size = (min_w, min_h) if min_w or min_h else None
        w.max_size = (max_w, max_h) if (max_w, max_h) != (UNBOUNDED, UNBOUNDED) else None
        return (w.min_size, w.max_size) != before

    # ------------------------------------------------------------------ commands

    def focus(self, w: Window | None) -> None:
        """Focus `w`, or the best candidate on the current monitor if None (dwm's focus(NULL))."""
        if w is None:
            w = self.selected(self.cur)
        if w is None:
            return
        mon = self.monitor_of(w)
        self.selmon = self.monitors.index(mon)
        mon.stack.remove(w.id)
        mon.stack.insert(0, w.id)
        self._focus_request = w.id

    def focus_stack(self, direction: int) -> None:
        visible = self.visible(self.cur)
        if not visible:
            return
        sel = self.selected()
        i = visible.index(sel) if sel in visible else -direction
        self.focus(visible[(i + direction) % len(visible)])

    def inc_nmaster(self, delta: int) -> None:
        s = self.cur.settings
        s.nmaster = max(0, s.nmaster + delta)

    def set_mfact(self, delta: float) -> None:
        s = self.cur.settings
        if LAYOUTS[s.layout].arrange is None:
            return
        f = s.mfact + delta
        if 0.05 <= f <= 0.95:
            s.mfact = round(f, 4)

    def zoom(self) -> None:
        """Promote the focused window to master (or swap the master with the next window)."""
        mon, sel = self.cur, self.selected()
        if sel is None or sel.floating or LAYOUTS[mon.settings.layout].arrange is None:
            return
        tiled = [w for w in self.visible(mon) if not w.floating]
        if sel is tiled[0]:
            if len(tiled) < 2:
                return
            sel = tiled[1]
        mon.order.remove(sel.id)
        mon.order.insert(0, sel.id)
        self.focus(sel)

    def _mask(self, tag: int) -> int:
        return self.cur.all_mask if tag == 0 else 1 << (tag - 1)

    def view(self, tag: int) -> None:
        """tag 1..n selects one tag; 0 selects them all."""
        self.cur.view(self._mask(tag))
        self.focus(None)

    def view_previous(self) -> None:
        self.cur.view(0)
        self.focus(None)

    def toggle_view(self, tag: int) -> None:
        self.cur.toggle_view(self._mask(tag))
        self.focus(None)

    def tag(self, tag: int) -> None:
        """Move the focused window to a tag (0 = every tag)."""
        if (sel := self.selected()) is not None:
            sel.tags = self._mask(tag)
            self.focus(None)

    def toggle_tag(self, tag: int) -> None:
        if (sel := self.selected()) is not None and (new := sel.tags ^ self._mask(tag)):
            sel.tags = new
            self.focus(None)

    def kill(self) -> None:
        if (sel := self.selected()) is not None:
            self._actions.append(Close(sel.id))

    def set_layout(self, name: str) -> None:
        s = self.cur.settings
        if name not in LAYOUTS:
            raise ValueError(f"unknown layout {name!r}; choose from {sorted(LAYOUTS)}")
        if name == s.layout:
            self.toggle_layout()
        else:
            s.prev_layout, s.layout = s.layout, name

    def toggle_layout(self) -> None:
        s = self.cur.settings
        s.layout, s.prev_layout = s.prev_layout, s.layout

    def toggle_floating(self) -> None:
        if (sel := self.selected()) is not None:
            sel.floating = not sel.floating

    def toggle_bar(self) -> None:
        if self.config.BAR_ENABLED:  # with the bar disabled there is nothing to toggle
            self.cur.show_bar = not self.cur.show_bar

    def _other_monitor(self, direction: int) -> int | None:
        if len(self.monitors) < 2:
            return None
        return (self.selmon + direction) % len(self.monitors)

    def focus_monitor(self, direction: int) -> None:
        if (i := self._other_monitor(direction)) is not None:
            self.selmon = i
            self.focus(None)

    def tag_monitor(self, direction: int) -> None:
        """Send the focused window to the next monitor."""
        sel, i = self.selected(), self._other_monitor(direction)
        if sel is None or i is None:
            return
        src, dst = self.cur, self.monitors[i]
        src.order.remove(sel.id)
        src.stack.remove(sel.id)
        sel.monitor, sel.tags = dst.id, dst.tagset
        dst.order.insert(0, sel.id)
        dst.stack.insert(0, sel.id)
        self.focus(None)

    def spawn(self, argv: tuple[str, ...]) -> None:
        self._actions.append(Spawn(argv))

    def quit(self) -> None:
        self._actions.append(Quit())

    # ------------------------------------------------------------------ output

    def flush(self) -> Plan:
        """Compute what the world should look like. Cheap, pure, and safe to call any time."""
        placements: dict[WindowId, Placement] = {}
        raise_order: list[WindowId] = []
        for mon in self.monitors:
            live = [w for w in (self.windows[i] for i in mon.order) if not w.suspended]
            shown = [w for w in live if w.tags & mon.tagset]
            for w in live:
                if w not in shown:
                    placements[w.id] = Hide()
            s = mon.settings
            layout = LAYOUTS[s.layout]
            tiled = [w for w in shown if not w.floating]
            rects = arrange(layout, mon.area, len(tiled), s.nmaster, s.mfact, self.config.GAP)
            if rects:  # the float layout has no arrange function, so no rects
                for w, rect in zip(tiled, rects, strict=True):
                    placements[w.id] = Show(fit(rect, mon.area, w.min_size, w.max_size))
            if layout.overlaps and (sel := self.selected(mon)) is not None and not sel.floating:
                raise_order.append(sel.id)
            for w in shown:
                placements.setdefault(w.id, Show(None))
            raise_order += [w.id for w in shown if w.floating]  # floating windows stay on top

        focus = None
        if (wid := self._focus_request) is not None and isinstance(placements.get(wid), Show):
            focus = wid
        self._focus_request = None
        actions, self._actions = tuple(self._actions), []
        self.changed.emit(self.status())
        return Plan(placements, focus, tuple(raise_order), actions)

    def status(self) -> list[MonitorStatus]:
        out = []
        for i, mon in enumerate(self.monitors):
            occupied = 0
            for wid in mon.order:
                occupied |= self.windows[wid].tags
            sel = self.selected(mon)
            out.append(
                MonitorStatus(
                    mon.id,
                    i == self.selmon,
                    self.config.TAGS,
                    occupied,
                    mon.tagset,
                    LAYOUTS[mon.settings.layout].symbol,
                    sel.title if sel else "",
                    mon.bar_rect,
                )
            )
        return out
