"""macos/view.py and macos/window.py without showing a window: the view is drawn into a bitmap."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="AppKit")


def _rgb(color):
    """A pixel's colour as 0..255 sRGB. The bitmap is in "Generic RGB", so convert before comparing with
    colours that were specified in sRGB (0x222222 reads back as 26 there, which is the same colour)."""
    from AppKit import NSColorSpace

    color = color.colorUsingColorSpace_(NSColorSpace.sRGBColorSpace())
    return (
        round(color.redComponent() * 255),
        round(color.greenComponent() * 255),
        round(color.blueComponent() * 255),
    )


def _pixel(rep, scale, x, y):
    return _rgb(rep.colorAtX_y_(int(x * scale), int(y * scale)))


def _close(a, b, tolerance=6):
    return all(abs(p - q) <= tolerance for p, q in zip(a, b, strict=True))


def vertical_menu(per_page=3, lines=3, items=("alpha", "beta", "gamma", "delta")):
    from pymenu.config import Settings
    from pymenu.macos.view import make_style, make_view, render
    from pymenu.menu import Menu

    settings = Settings(lines=lines)
    style = make_style(settings)
    menu = Menu(list(items), lines=lines, per_page=per_page)
    view = make_view(400, menu, settings, style)
    rep = render(view)
    return menu, style, rep, rep.pixelsWide() / 400


def test_font_specs():
    from pymenu.macos.view import parse_font

    assert parse_font("Menlo:size=20").pointSize() == 20
    assert parse_font("monospace:size=11").pointSize() == 11
    assert parse_font("No Such Font:size=9").pointSize() == 9  # falls back instead of failing


def test_a_row_is_one_line_of_text_plus_two_pixels():
    from pymenu.config import Settings
    from pymenu.macos.view import make_style

    style = make_style(Settings())
    assert style.line_height > 0 and style.bh == style.line_height + 2


def test_the_view_is_one_row_for_the_input_plus_one_per_line():
    _, style, rep, scale = vertical_menu(lines=3)
    assert rep.pixelsHigh() == round(4 * style.bh * scale)


def test_selected_marked_and_normal_rows_use_their_own_colours():
    menu, style, rep, scale = vertical_menu()
    menu.select_next()  # the second row is selected
    menu.accept(ctrl=True)  # ... and marked; being selected it keeps the selected colours
    menu.select_next()  # now the third row is selected, and the second is only marked
    rep = _redraw(menu, style)
    scale = rep.pixelsWide() / 400
    far_right = 395  # no text out here, so the pixel is pure background
    row = lambda n: (n + 0.5) * style.bh  # noqa: E731  (the vertical middle of row n; row 0 is the input)
    assert _close(_pixel(rep, scale, far_right, row(0)), (0x22, 0x22, 0x22))  # the input field: normal
    assert _close(_pixel(rep, scale, far_right, row(2)), (0x00, 0xFF, 0xFF))  # marked: the "out" scheme
    assert _close(_pixel(rep, scale, far_right, row(3)), (0x00, 0x55, 0x77))  # selected


def _redraw(menu, style):
    from pymenu.config import Settings
    from pymenu.macos.view import make_view, render

    return render(make_view(400, menu, Settings(lines=menu.lines), style))


def test_menu_rect_sits_on_the_top_or_the_bottom_edge():
    from pymenu.macos.window import menu_rect

    screen = (100.0, 50.0, 1440.0, 900.0)  # AppKit coordinates: y grows upwards
    assert menu_rect(screen, 20, topbar=True) == (100.0, 930.0, 1440.0, 20)
    assert menu_rect(screen, 20, topbar=False) == (100.0, 50.0, 1440.0, 20)


def test_a_horizontal_page_never_holds_more_items_than_fit():
    from pymenu.config import Settings
    from pymenu.macos.view import cell_width, make_style
    from pymenu.macos.window import fit_per_page
    from pymenu.menu import Menu

    settings = Settings()
    style = make_style(settings)
    short = Menu(["ab"] * 30)
    long = Menu(["x" * 400] * 3)
    assert fit_per_page(short, settings, style, 1000) > fit_per_page(
        Menu(["abcdefghij"] * 30), settings, style, 1000
    )
    assert fit_per_page(long, settings, style, 1000) == 1  # too wide for even one: still one, clipped
    assert fit_per_page(short, settings, style, 1000) * cell_width(style, "ab") <= 1000


def test_pick_screen_always_finds_a_screen():
    from AppKit import NSApplication

    from pymenu.macos.window import pick_screen

    NSApplication.sharedApplication()
    assert pick_screen(-1) is not None and pick_screen(99) is not None


def test_centred_menu_rect_is_in_the_middle_both_ways():
    from pymenu.macos.window import menu_rect

    screen = (100.0, 50.0, 1440.0, 900.0)
    # 700 wide, 200 high: (1440 - 700) / 2 = 370 from the left edge, (900 - 200) / 2 = 350 from the bottom
    assert menu_rect(screen, 200, topbar=True, center_width=700) == (470.0, 400.0, 700, 200)
    assert menu_rect(screen, 200, topbar=False, center_width=700) == (470.0, 400.0, 700, 200)  # -b is ignored


def test_a_centred_menu_never_exceeds_ninety_percent_of_a_small_screen():
    from pymenu.macos.window import menu_rect

    x, _, width, _ = menu_rect((0.0, 0.0, 600.0, 400.0), 100, topbar=True, center_width=700)
    assert width == 540.0 and x == 30.0  # 90% of 600, centred


def test_the_uncentred_rect_is_unchanged():
    from pymenu.macos.window import menu_rect

    screen = (100.0, 50.0, 1440.0, 900.0)
    assert menu_rect(screen, 20, topbar=True) == (100.0, 930.0, 1440.0, 20)
