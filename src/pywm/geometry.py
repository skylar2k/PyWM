"""Rectangles and the *one* coordinate conversion function.

Everything in pywm lives in **AX coordinates**: the origin is the top-left corner
of the primary display, x grows right, y grows *down*. CoreGraphics
(`CGDisplayBounds`) already speaks this language. AppKit (`NSScreen.frame`,
`visibleFrame`) does not: its origin is the *bottom*-left of the primary display
and y grows *up*. `flip_y` is the only place that difference is handled.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    """An integer rectangle. Frozen, so it can be a dict key and never changes under you."""

    x: int
    y: int
    w: int
    h: int

    @classmethod
    def from_floats(cls, x: float, y: float, w: float, h: float) -> Rect:
        return cls(round(x), round(y), round(w), round(h))

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    def inset(self, n: int) -> Rect:
        """Shrink by `n` on every side (grow if negative). Never goes below 1x1."""
        return Rect(self.x + n, self.y + n, max(1, self.w - 2 * n), max(1, self.h - 2 * n))

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom

    def overlap_area(self, other: Rect) -> int:
        w = min(self.right, other.right) - max(self.x, other.x)
        h = min(self.bottom, other.bottom) - max(self.y, other.y)
        return w * h if w > 0 and h > 0 else 0

    def close_to(self, other: Rect, tolerance: int = 2) -> bool:
        """Compare two frames allowing for the rounding apps like to do."""
        return all(
            abs(a - b) <= tolerance
            for a, b in ((self.x, other.x), (self.y, other.y), (self.w, other.w), (self.h, other.h))
        )


def union(rects: list[Rect]) -> Rect:
    left = min(r.x for r in rects)
    top = min(r.y for r in rects)
    return Rect(left, top, max(r.right for r in rects) - left, max(r.bottom for r in rects) - top)


def flip_y(rect: Rect, primary_height: int) -> Rect:
    """Convert between AppKit (bottom-left origin) and AX (top-left origin) coordinates.

    The same formula works in both directions because flipping twice is a no-op.
    `primary_height` is the height of the *primary* display (the one with the menu
    bar), because both systems anchor their origin to it, even for other displays.
    """
    return Rect(rect.x, primary_height - (rect.y + rect.h), rect.w, rect.h)
