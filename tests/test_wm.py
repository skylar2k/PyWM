"""Behaviour of the pure window manager, driven with hand-made WindowInfo snapshots."""

import pytest
from helpers import make_config

from pywm.core.rules import Rule
from pywm.core.types import Hide, Screen, Show, WindowInfo
from pywm.core.wm import WindowManager
from pywm.geometry import Rect

SCREEN = Screen(1, "main", Rect(0, 0, 1000, 600), Rect(0, 0, 1000, 600))
SCREEN2 = Screen(2, "right", Rect(1000, 0, 1000, 600), Rect(1000, 0, 1000, 600))


DEFAULT_FRAME = Rect(100, 100, 400, 300)


def info(wid, pid=1, app="App", subrole="AXStandardWindow", frame=DEFAULT_FRAME, **kw):
    return WindowInfo(wid, pid, app, f"com.{app}", f"{app} {wid}", subrole, frame, **kw)


def make(*wids, config=None, screens=(SCREEN,)):
    wm = WindowManager(config or make_config())
    wm.set_screens(list(screens))
    wm.sync_app(1, [info(w) for w in wids])
    return wm


def rects(wm):
    return {i: p.rect for i, p in wm.flush().placements.items() if isinstance(p, Show)}


# --- adoption ---------------------------------------------------------------------


def test_new_windows_become_master_like_dwm():
    wm = make(1, 2, 3)
    assert wm.cur.order == [3, 2, 1]


def test_only_standard_windows_are_tiled_dialogs_float_the_rest_is_ignored():
    wm = make()
    wm.sync_app(1, [info(1), info(2, subrole="AXDialog"), info(3, subrole="AXUnknown")])
    assert set(wm.windows) == {1, 2}
    assert not wm.windows[1].floating and wm.windows[2].floating


def test_tiled_windows_are_laid_out_and_floating_ones_left_alone():
    wm = make()
    wm.sync_app(1, [info(1), info(2, subrole="AXDialog")])
    plan = wm.flush()
    assert isinstance(plan.placements[1].rect, Rect)
    assert plan.placements[2] == Show(None)


def test_rules_set_floating_tag_and_ignore():
    cfg = make_config(
        RULES=[Rule(app="Float", floating=True), Rule(app="Slack", tag=3), Rule(app="Nope", ignore=True)]
    )
    wm = make(config=cfg)
    wm.sync_app(1, [info(1, app="Float"), info(2, app="Slack"), info(3, app="Nope")])
    assert wm.windows[1].floating
    assert wm.windows[2].tags == 0b100
    assert 3 not in wm.windows


def test_non_resizable_windows_float_by_default():
    wm = make()
    wm.sync_app(1, [info(1, resizable=False)])
    assert wm.windows[1].floating


# --- tags ---------------------------------------------------------------------------


def test_view_hides_other_tags_and_view_back_restores():
    wm = make(1, 2)
    wm.tag(2)  # window 2 (focused? selected is the newest focus) goes to tag 2
    moved = next(w for w in wm.windows.values() if w.tags == 0b10)
    plan = wm.flush()
    assert plan.placements[moved.id] == Hide()
    wm.view(2)
    plan = wm.flush()
    assert isinstance(plan.placements[moved.id], Show)
    other = next(i for i in wm.windows if i != moved.id)
    assert plan.placements[other] == Hide()


def test_view_previous_flips_between_two_views():
    wm = make(1)
    wm.view(3)
    wm.view_previous()
    assert wm.cur.tagset == 0b1
    wm.view_previous()
    assert wm.cur.tagset == 0b100


def test_view_all_and_toggle_view():
    wm = make(1)
    wm.view(0)
    assert wm.cur.tagset == wm.cur.all_mask
    wm.view(2)
    wm.toggle_view(3)
    assert wm.cur.tagset == 0b110
    wm.toggle_view(2)
    wm.toggle_view(3)  # would leave nothing selected: refused
    assert wm.cur.tagset == 0b100


def test_each_tag_remembers_its_own_layout_and_master_factor():
    wm = make(1, 2)
    wm.set_layout("monocle")
    wm.view(2)
    assert wm.cur.settings.layout == "tile"
    wm.set_mfact(0.1)
    wm.view(1)
    assert wm.cur.settings.layout == "monocle"
    assert wm.cur.settings.mfact == 0.55


def test_toggle_tag_never_leaves_a_window_with_no_tags():
    wm = make(1)
    wm.toggle_tag(1)
    assert wm.windows[1].tags == 0b1
    wm.toggle_tag(2)
    assert wm.windows[1].tags == 0b11


# --- focus ----------------------------------------------------------------------------


def test_focus_stack_cycles_in_tiling_order_and_wraps():
    wm = make(1, 2, 3)  # order is [3, 2, 1]; 3 is focused (most recently added)
    wm.window_focused(3)
    seen = []
    for _ in range(4):
        wm.focus_stack(1)
        seen.append(wm.selected().id)
        wm.flush()
    assert seen == [2, 1, 3, 2]
    wm.focus_stack(-1)
    assert wm.selected().id == 3


def test_flush_requests_focus_only_for_commands_not_for_os_events():
    wm = make(1, 2)
    wm.window_focused(1)
    assert wm.flush().focus is None
    wm.focus_stack(1)
    assert wm.flush().focus is not None
    assert wm.flush().focus is None  # one-shot


def test_closing_the_focused_window_hands_focus_to_the_next():
    wm = make(1, 2, 3)
    wm.window_focused(3)
    wm.flush()
    wm.sync_app(1, [info(1), info(2)])
    assert wm.flush().focus in (1, 2)


def test_os_focusing_a_window_on_a_hidden_tag_switches_to_that_tag():
    wm = make(1, 2)
    wm.window_focused(1)
    wm.tag(4)
    wm.flush()
    assert wm.cur.tagset == 0b1
    wm.window_focused(1)
    assert wm.cur.tagset == 0b1000


def test_zoom_promotes_to_master_or_swaps_with_next():
    wm = make(1, 2, 3)  # [3, 2, 1]
    wm.window_focused(1)
    wm.zoom()
    assert wm.cur.order == [1, 3, 2]
    wm.zoom()  # already master: swap with the next tiled window
    assert wm.cur.order[0] == 3


def test_zoom_does_nothing_in_float_layout():
    wm = make(1, 2)
    wm.set_layout("float")
    before = list(wm.cur.order)
    wm.zoom()
    assert wm.cur.order == before


# --- suspended windows --------------------------------------------------------------


@pytest.mark.parametrize("flag", ["fullscreen", "minimized", "away"])
def test_suspended_windows_are_not_tiled_but_keep_their_place(flag):
    wm = make(1, 2)
    wm.sync_app(1, [info(1), info(2, **{flag: True})])
    plan = wm.flush()
    assert 2 not in plan.placements
    assert plan.placements[1].rect == wm.cur.area  # the other window gets the whole screen
    wm.sync_app(1, [info(1), info(2)])
    assert 2 in wm.flush().placements


def test_window_on_another_space_is_kept_not_forgotten():
    wm = make(1, 2)
    wm.sync_app(1, [info(1)], exists=lambda wid: wid == 2)
    assert 2 in wm.windows and wm.windows[2].away


def test_truly_closed_window_is_forgotten():
    wm = make(1, 2)
    wm.sync_app(1, [info(1)], exists=lambda wid: False)
    assert 2 not in wm.windows


# --- layouts and sizes ------------------------------------------------------------


def test_learned_minimum_size_changes_the_next_layout():
    wm = make(1, 2)
    r = rects(wm)[1]
    assert wm.learn_size(1, r, Rect(r.x, r.y, r.w + 200, r.h))
    assert not wm.learn_size(1, r, Rect(r.x, r.y, r.w + 200, r.h))  # no news the second time
    assert rects(wm)[1].w >= r.w + 200


def test_monocle_raises_the_selected_window_and_floats_stay_on_top():
    wm = make(1, 2)
    wm.sync_app(1, [info(1), info(2), info(3, subrole="AXDialog")])
    wm.set_layout("monocle")
    wm.focus(wm.windows[1])
    order = wm.flush().raise_order
    assert order[0] == 1 and order[-1] == 3


def test_nmaster_and_mfact_commands():
    wm = make(1, 2, 3)
    wm.inc_nmaster(1)
    assert wm.cur.settings.nmaster == 2
    wm.inc_nmaster(-5)
    assert wm.cur.settings.nmaster == 0
    wm.set_mfact(0.9)  # would exceed the 0.95 limit
    assert wm.cur.settings.mfact == 0.55


# --- monitors -------------------------------------------------------------------------


def test_monitors_are_ordered_left_to_right_and_windows_land_where_they_are():
    wm = WindowManager(make_config())
    wm.set_screens([SCREEN2, SCREEN])
    assert [m.id for m in wm.monitors] == [1, 2]
    wm.sync_app(1, [info(1, frame=Rect(1200, 100, 300, 300))])
    assert wm.windows[1].monitor == 2


def test_tag_monitor_moves_the_window_and_focus_monitor_switches():
    wm = make(1, 2, screens=(SCREEN, SCREEN2))
    wm.window_focused(1)
    start = wm.cur
    wm.tag_monitor(1)
    assert wm.windows[1].monitor == wm.monitors[1].id
    assert wm.cur is start  # like dwm's tagmon: the window moves, focus stays on this monitor
    wm.focus_monitor(1)
    assert wm.cur is wm.monitors[1] and wm.selected().id == 1
    wm.focus_monitor(-1)
    assert wm.cur is start


def test_unplugging_a_monitor_moves_its_windows_to_the_remaining_one():
    wm = make(1, screens=(SCREEN, SCREEN2))
    wm.sync_app(1, [info(1), info(2, frame=Rect(1200, 100, 300, 300))])
    wm.set_screens([SCREEN])
    assert {w.monitor for w in wm.windows.values()} == {1}
    assert set(wm.monitors[0].order) == {1, 2}


def test_status_reports_what_a_bar_needs():
    wm = make(1)
    wm.tag(3)
    (status,) = wm.status()
    assert status.occupied == 0b100 and status.selected == 0b1 and status.layout_symbol == "[]="


def test_changed_signal_fires_on_flush():
    wm = make(1)
    seen = []
    wm.changed.connect(seen.append)
    wm.flush()
    assert len(seen) == 1


# --- bar placement ------------------------------------------------------------------

NOTCHED = Screen(1, "main", Rect(0, 0, 1800, 1169), Rect(0, 38, 1800, 1131))  # 38px reserved at the top
UNRESERVED = Screen(1, "main", Rect(0, 0, 1800, 1169), Rect(0, 0, 1800, 1169))


def bar_monitor(screen: Screen, covers: bool):
    wm = WindowManager(make_config(BAR_ENABLED=True, BAR_HEIGHT=24, BAR_COVERS_MENU=covers))
    wm.set_screens([screen])
    return wm.cur


def test_bar_normally_sits_below_the_reserved_band_and_takes_layout_space():
    mon = bar_monitor(NOTCHED, covers=False)
    assert mon.bar_rect == Rect(0, 38, 1800, 24)
    assert mon.area == Rect(0, 62, 1800, 1107)


def test_covering_bar_fills_the_reserved_band_and_loses_no_space():
    mon = bar_monitor(NOTCHED, covers=True)
    assert mon.bar_rect == Rect(0, 0, 1800, 38)  # as tall as the band it replaces
    assert mon.area == Rect(0, 38, 1800, 1131)  # windows start where they always did


def test_covering_bar_on_a_display_with_no_reserved_band_takes_its_own_height():
    mon = bar_monitor(UNRESERVED, covers=True)
    assert mon.bar_rect == Rect(0, 0, 1800, 24)
    assert mon.area == Rect(0, 24, 1800, 1145)
