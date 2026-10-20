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
