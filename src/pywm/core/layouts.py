"""Layouts are pure functions: (area, how many windows, knobs) -> one rect per window.

This is the Strategy pattern (*Software Design for Python Programmers*, ch. 8;
*Fluent Python*, ch. 10): because functions are first-class objects, a "strategy"
is just a function plus a name, with no class hierarchy needed.

To add a layout, write a function with the `Arrange` signature, wrap it in
`Layout(...)` and add it to `LAYOUTS`. The README has a worked example.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pywm.core.types import Size
from pywm.geometry import Rect

type Arrange = Callable[[Rect, int, int, float], list[Rect]]
"""(area, n_windows, nmaster, mfact) -> n_windows rects"""


@dataclass(frozen=True, slots=True)
class Layout:
    name: str
    symbol: str  # shown in the bar, exactly like dwm's layout symbol
    arrange: Arrange | None  # None means "leave windows where they are"
    overlaps: bool = False  # windows stack on top of each other, so z-order matters


def tile(area: Rect, n: int, nmaster: int, mfact: float) -> list[Rect]:
    """dwm's classic layout: a master column on the left, a stack on the right."""
    if n == 0:
        return []
    nmaster = min(nmaster, n)
    master_w = int(area.w * mfact) if 0 < nmaster < n else (area.w if nmaster else 0)
    rects: list[Rect] = []
    my = ty = 0  # how far down each column we have already used
    for i in range(n):
        if i < nmaster:
            h = (area.h - my) // (nmaster - i)
            rects.append(Rect(area.x, area.y + my, master_w, h))
            my += h
        else:
            h = (area.h - ty) // (n - i)
            rects.append(Rect(area.x + master_w, area.y + ty, area.w - master_w, h))
            ty += h
    return rects


def bstack(area: Rect, n: int, nmaster: int, mfact: float) -> list[Rect]:
    """Like tile, rotated: masters across the top, the stack across the bottom."""
    if n == 0:
        return []
    nmaster = min(nmaster, n)
    master_h = int(area.h * mfact) if 0 < nmaster < n else (area.h if nmaster else 0)
    rects: list[Rect] = []
    mx = tx = 0
    for i in range(n):
        if i < nmaster:
            w = (area.w - mx) // (nmaster - i)
            rects.append(Rect(area.x + mx, area.y, w, master_h))
            mx += w
        else:
            w = (area.w - tx) // (n - i)
            rects.append(Rect(area.x + tx, area.y + master_h, w, area.h - master_h))
            tx += w
    return rects


def monocle(area: Rect, n: int, nmaster: int, mfact: float) -> list[Rect]:
    """Every window fills the whole area; the focused one is raised on top."""
    return [area] * n


LAYOUTS: dict[str, Layout] = {
    layout.name: layout
    for layout in (
        Layout("tile", "[]=", tile),
        Layout("float", "><>", None),
        Layout("monocle", "[M]", monocle, overlaps=True),
        Layout("bstack", "TTT", bstack),
    )
}


def arrange(layout: Layout, area: Rect, n: int, nmaster: int, mfact: float, gap: int) -> list[Rect]:
    """Run a layout inside `area`, leaving `gap` pixels between windows and at the edges.

    Trick: shrink the area by (gap - gap//2), run the layout, then shrink every
    rect by gap//2. Neighbours each give up gap//2, so the space between them is
    gap (rounded down to even), and the outer margin is exactly gap.
    """
    if layout.arrange is None or n == 0:
        return []
    half = gap // 2
    rects = layout.arrange(area.inset(gap - half), n, nmaster, mfact)
    return [r.inset(half) for r in rects] if half else rects


def fit(rect: Rect, area: Rect, min_size: Size | None, max_size: Size | None) -> Rect:
    """Adapt a slot to what a stubborn window will actually accept.

    Some apps refuse to be smaller (or bigger) than some size. We learn those
    limits by watching what the app really did (see Controller). dwm does the
    same with size hints: when a window will not fit its slot, it overflows the
    slot, but we pull it back inside the work area so it never wanders off screen.
    """
    w, h = rect.w, rect.h
    if min_size:
        w, h = max(w, min_size[0]), max(h, min_size[1])
    if max_size:
        w, h = min(w, max_size[0]), min(h, max_size[1])
    x = min(rect.x, area.right - w)
    y = min(rect.y, area.bottom - h)
    return Rect(max(x, area.x), max(y, area.y), w, h)
