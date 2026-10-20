import pytest

from pywm.core.layouts import LAYOUTS, arrange, bstack, fit, monocle, tile
from pywm.geometry import Rect

AREA = Rect(0, 0, 1000, 600)


def covers_area_without_overlap(rects: list[Rect], area: Rect) -> bool:
    total = sum(r.w * r.h for r in rects)
    pairwise = sum(a.overlap_area(b) for i, a in enumerate(rects) for b in rects[i + 1 :])
    return total == area.w * area.h and pairwise == 0


def test_tile_single_window_fills_area():
    assert tile(AREA, 1, 1, 0.55) == [AREA]


def test_tile_master_and_stack():
    m, s1, s2 = tile(AREA, 3, 1, 0.5)
    assert m == Rect(0, 0, 500, 600)
    assert s1 == Rect(500, 0, 500, 300)
    assert s2 == Rect(500, 300, 500, 300)


@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize("nmaster", range(0, 4))
def test_tile_never_overlaps_or_leaves_holes(n, nmaster):
    rects = tile(AREA, n, nmaster, 0.55)
    assert len(rects) == n
    assert covers_area_without_overlap(rects, AREA)


def test_tile_with_no_master_puts_everything_in_the_stack():
    rects = tile(AREA, 2, 0, 0.5)
    assert all(r.x == 0 and r.w == 1000 for r in rects)


def test_bstack_is_tile_rotated():
    top, b1, b2 = bstack(AREA, 3, 1, 0.5)
    assert top == Rect(0, 0, 1000, 300)
    assert (b1.w, b2.w) == (500, 500) and b1.y == 300


def test_monocle_gives_everyone_the_whole_area():
    assert monocle(AREA, 3, 1, 0.5) == [AREA] * 3


def test_gaps_leave_the_requested_margin_between_windows_and_edges():
    a, b = arrange(LAYOUTS["tile"], AREA, 2, 1, 0.5, gap=10)
    assert a.x == 10 and a.y == 10 and b.right == 990 and b.bottom == 590
    assert b.x - a.right == 10


def test_float_layout_arranges_nothing():
    assert arrange(LAYOUTS["float"], AREA, 3, 1, 0.5, gap=0) == []


def test_fit_grows_to_minimum_size_but_stays_inside_the_area():
    slot = Rect(800, 400, 200, 200)  # bottom-right corner slot
    fitted = fit(slot, AREA, (400, 300), None)
    assert (fitted.w, fitted.h) == (400, 300)
    assert fitted.right <= AREA.right and fitted.bottom <= AREA.bottom


def test_fit_honours_maximum_size():
    assert fit(AREA, AREA, None, (300, 200)).w == 300
