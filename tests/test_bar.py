import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="the bar is AppKit")


def test_bar_view_renders_a_png_without_a_screen():
    from helpers import make_config

    from pywm.bar.view import make_view, snapshot_png
    from pywm.core.wm import MonitorStatus
    from pywm.geometry import Rect

    cfg = make_config()
    view = make_view(600, 24, cfg.BAR_FONT_SIZE, cfg.COLORS)
    view.status = MonitorStatus(1, True, cfg.TAGS, 0b101, 0b100, "[]=", "title", Rect(0, 0, 600, 24))
    png = snapshot_png(view)
    assert png.startswith(b"\x89PNG") and len(png) > 500


def _status(**overrides):
    from helpers import make_config

    from pywm.core.wm import MonitorStatus
    from pywm.geometry import Rect

    fields = dict(
        monitor=1, current=True, tag_names=make_config().TAGS, occupied=0b101, selected=0b1,
        layout_symbol="[]=", title="a title", bar_rect=Rect(0, 0, 1800, 38),
    )  # fmt: skip
    return MonitorStatus(**{**fields, **overrides})


def _font():
    from helpers import make_config

    from pywm.bar.view import make_view

    cfg = make_config()
    return make_view(1, 1, cfg.BAR_FONT_SIZE, cfg.COLORS).font


def test_content_width_covers_every_tag_and_the_layout_symbol():
    from pywm.bar.view import cell_width, content_width

    font, status = _font(), _status()
    expected = sum(cell_width(font, t) for t in status.tag_names) + cell_width(font, "[]=")
    assert content_width(font, status) == expected > 0


def test_content_width_grows_with_more_tags_and_follows_the_layout_symbol():
    from pywm.bar.view import content_width

    font = _font()
    assert content_width(font, _status(tag_names=("1", "2"))) < content_width(font, _status())
    assert content_width(font, _status(layout_symbol="[]=")) != content_width(
        font, _status(layout_symbol="TTT")
    )


def test_the_window_title_is_not_part_of_the_indicator():
    from pywm.bar.view import content_width

    font = _font()
    assert content_width(font, _status(title="x")) == content_width(
        font, _status(title="a very long title" * 5)
    )


def test_compact_frame_starts_at_the_anchor_and_fills_the_band_vertically():
    from pywm.bar.bar import compact_frame
    from pywm.geometry import Rect

    band = Rect(0, 0, 1800, 38)
    assert compact_frame(band, 287.9, anchor_x=1010) == Rect(1010, 0, 288, 38)


def test_compact_frame_never_runs_past_the_right_edge_or_the_left_one():
    from pywm.bar.bar import compact_frame
    from pywm.geometry import Rect

    band = Rect(1800, 0, 1000, 30)  # a second display to the right
    assert compact_frame(band, 300, anchor_x=2700) == Rect(2500, 0, 300, 30)  # pulled back inside
    assert compact_frame(band, 300, anchor_x=100).x == 1800  # and not left of the display
    assert compact_frame(band, 5000, anchor_x=1900).w == 1000  # and never wider than the display
