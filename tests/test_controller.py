"""The shell and the core together, running against FakePlatform."""

from pywm.core.wm import WindowManager as WM
from pywm.geometry import Rect
from pywm.platform.events import AppLaunched, AppTerminated, ScreensChanged, WindowsChanged


def start(ctl):
    ctl.start()
    return ctl.platform


def calls(platform, kind):
    return [entry for entry in platform.log if entry[0] == kind]


def test_start_tiles_existing_windows(ctl, platform):
    a, b = platform.add_window(), platform.add_window()
    start(ctl)
    frames = platform.visible_frames()
    assert frames[b].x == 0  # newest is master, on the left
    assert frames[a].x == frames[b].right
    assert frames[a].h == ctl.wm.cur.area.h


def test_new_window_triggers_a_relayout(ctl, platform):
    a = platform.add_window()
    start(ctl)
    b = platform.add_window()
    ctl.handle(WindowsChanged(platform.windows[b].pid))
    platform.run_timers()
    assert platform.windows[a].frame.w < ctl.wm.cur.area.w


def test_bursts_of_events_cause_one_resync(ctl, platform):
    a = platform.add_window()
    start(ctl)
    platform.timers.clear()
    for _ in range(20):
        ctl.handle(WindowsChanged(platform.windows[a].pid))
    assert len(platform.timers) == 1


def test_closed_window_is_removed_and_the_rest_fill_the_space(ctl, platform):
    a, b = platform.add_window(), platform.add_window()
    start(ctl)
    owner = platform.windows[b].pid
    platform.remove_window(b)
    ctl.handle(WindowsChanged(owner))  # the notification comes from the app that lost the window
    platform.run_timers()
    assert platform.windows[a].frame == ctl.wm.cur.area


def test_terminated_app_forgets_its_windows(ctl, platform):
    a = platform.add_window(pid=7)
    start(ctl)
    ctl.handle(AppTerminated(7))
    assert a not in ctl.wm.windows


def test_launch_retries_until_the_app_is_ready(ctl, platform):
    start(ctl)
    ctl.handle(AppLaunched(42))
    a = platform.add_window(pid=42)  # the window only shows up after the app has settled
    platform.run_timers()
    assert a in ctl.wm.windows


def test_view_hides_and_restores_windows(ctl, platform):
    a, b = platform.add_window(), platform.add_window()
    start(ctl)
    ctl.wm.window_focused(b)
    ctl.execute(WM.tag, 2)
    assert platform.windows[b].saved_frame is not None  # parked
    ctl.execute(WM.view, 2)
    assert platform.windows[b].saved_frame is None and platform.windows[a].saved_frame is not None
    assert platform.focused == b
    ctl.execute(WM.view, 1)
    assert platform.windows[a].saved_frame is None


def test_stubborn_window_is_read_back_and_layout_adjusts(ctl, platform):
    platform.add_window()
    b = platform.add_window(min_size=(1100, 300))  # refuses to be narrower than 1100
    start(ctl)
    area = ctl.wm.cur.area
    fb = platform.windows[b].frame
    assert fb.w >= 1100 and fb.right <= area.right
    assert ctl.wm.windows[b].min_size == (1100, 0)  # the height never bound, so none is learned


def test_unchanged_placements_are_not_resent(ctl, platform):
    platform.add_window()
    start(ctl)
    platform.log.clear()
    ctl.apply()
    assert not calls(platform, "set_frame")


def test_kill_closes_the_focused_window(ctl, platform):
    a, _b = platform.add_window(), platform.add_window()
    start(ctl)
    ctl.wm.window_focused(a)
    ctl.execute(WM.kill)
    assert calls(platform, "close") == [("close", a)]
    assert a not in platform.windows


def test_quit_restores_hidden_windows(ctl, platform):
    a = platform.add_window()
    start(ctl)
    ctl.execute(WM.view, 5)
    assert platform.windows[a].saved_frame is not None
    ctl.execute(WM.quit)
    assert platform.windows[a].saved_frame is None
    assert ("stop",) in platform.log


def test_spawn_goes_through_the_platform(ctl, platform):
    start(ctl)
    ctl.execute(WM.spawn, ("echo", "hi"))
    assert calls(platform, "spawn") == [("spawn", ("echo", "hi"))]


def test_hung_app_does_not_lose_its_windows(ctl, platform):
    a = platform.add_window(pid=9)
    start(ctl)
    platform.window_infos = lambda pid: None  # every query times out
    ctl.handle(WindowsChanged(9))
    platform.run_timers()
    assert a in ctl.wm.windows


def test_hotkeys_cover_every_binding(ctl, platform, config):
    start(ctl)
    assert platform.grabbed == {k.chord for k in config.KEYS}


def test_screen_change_replans_with_new_work_area(ctl, platform):
    a = platform.add_window()
    start(ctl)
    s = platform.screen_list[0]
    platform.screen_list[0] = type(s)(s.id, s.name, Rect(0, 0, 800, 600), Rect(0, 0, 800, 600))
    ctl.handle(ScreensChanged())
    platform.run_timers()
    assert platform.windows[a].frame == Rect(0, 0, 800, 600)


def test_commands_act_on_the_window_the_os_says_is_focused(ctl, platform):
    """Regression: focus Claude, press 'send to tag 2', and Zed (pywm's remembered focus) moved instead."""
    zed, zen = platform.add_window("Zed"), platform.add_window("Zen")
    start(ctl)
    ctl.wm.window_focused(zed)  # what pywm remembers
    platform.focused = zen  # what the user did: clicked Zen, and no event reached pywm
    ctl.execute(WM.tag, 2)
    assert ctl.wm.windows[zen].tags == 0b10
    assert ctl.wm.windows[zed].tags == 0b01  # untouched
