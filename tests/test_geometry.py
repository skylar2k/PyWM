from pywm.geometry import Rect, flip_y, union


def test_flip_y_is_its_own_inverse():
    r = Rect(10, 40, 300, 200)
    assert flip_y(flip_y(r, 1000), 1000) == r


def test_flip_y_primary_display():
    # AppKit: a 1440x900 screen whose visibleFrame sits above a 70px Dock and under a 25px menu bar.
    visible_appkit = Rect(0, 70, 1440, 805)
    assert flip_y(visible_appkit, 900) == Rect(0, 25, 1440, 805)


def test_flip_y_display_above_the_primary_one():
    # In AppKit a monitor placed above the primary has y >= primary height; in AX it is negative.
    above = Rect(0, 900, 1440, 900)
    assert flip_y(above, 900) == Rect(0, -900, 1440, 900)


def test_overlap_and_union():
    a, b = Rect(0, 0, 10, 10), Rect(5, 5, 10, 10)
    assert a.overlap_area(b) == 25
    assert a.overlap_area(Rect(20, 20, 1, 1)) == 0
    assert union([a, b]) == Rect(0, 0, 15, 15)


def test_close_to_tolerates_rounding():
    assert Rect(0, 0, 100, 100).close_to(Rect(1, 0, 99, 101))
    assert not Rect(0, 0, 100, 100).close_to(Rect(0, 0, 110, 100))
