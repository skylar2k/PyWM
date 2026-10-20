"""One display and everything dwm remembers about it: tags, layout, master settings."""

from dataclasses import dataclass, field

from pywm.core.types import WindowId
from pywm.geometry import Rect


@dataclass(slots=True)
class TagSettings:
    """Layout knobs. Like dwm's 'pertag' patch, every tag keeps its own."""

    nmaster: int
    mfact: float
    layout: str
    prev_layout: str


@dataclass(slots=True)
class Monitor:
    id: int
    name: str
    frame: Rect
    work_area: Rect
    ntags: int = 9
    default_settings: TagSettings = field(default_factory=lambda: TagSettings(1, 0.55, "tile", "float"))
    bar_height: int = 0
    show_bar: bool = False
    bar_covers_menu: bool = False

    # dwm keeps two tagsets so you can flip back to the previous view.
    tagsets: list[int] = field(default_factory=lambda: [1, 1])
    sel: int = 0  # which of the two tagsets is current
    curtag: int = 1  # 1..ntags for a single tag, 0 for "all tags"
    prevtag: int = 1
    pertag: dict[int, TagSettings] = field(default_factory=dict)

    order: list[WindowId] = field(default_factory=list)  # tiling order (index 0 = master)
    stack: list[WindowId] = field(default_factory=list)  # focus history (index 0 = latest)

    def __post_init__(self) -> None:
        d = self.default_settings
        self.pertag = {
            i: TagSettings(d.nmaster, d.mfact, d.layout, d.prev_layout) for i in range(self.ntags + 1)
        }

    # --- derived values -----------------------------------------------------------

    @property
    def all_mask(self) -> int:
        return (1 << self.ntags) - 1

    @property
    def tagset(self) -> int:
        return self.tagsets[self.sel]

    @property
    def settings(self) -> TagSettings:
        return self.pertag[self.curtag]

    @property
    def bar_rect(self) -> Rect | None:
        """Where the bar is drawn, in AX coordinates.

        Normally just under the reserved top band (the top of the work area). With
        `bar_covers_menu` it starts at the very top of the display and is at least as tall as
        the band macOS reserves there (menu bar, or the notch's safe area), so it fills that band
        exactly instead of leaving a strip of it showing.
        """
        if not (self.show_bar and self.bar_height):
            return None
        if self.bar_covers_menu:
            reserved = self.work_area.y - self.frame.y  # 0 only on displays with no reserved band
            return Rect(self.frame.x, self.frame.y, self.frame.w, max(self.bar_height, reserved))
        return Rect(self.work_area.x, self.work_area.y, self.work_area.w, self.bar_height)

    @property
    def area(self) -> Rect:
        """The rectangle layouts may use: the work area minus whatever the bar takes from it."""
        a, bar = self.work_area, self.bar_rect
        if bar is None or bar.bottom <= a.y:  # no bar, or it sits entirely in the reserved band
            return a
        return Rect(a.x, bar.bottom, a.w, max(1, a.bottom - bar.bottom))

    def _tag_index(self, mask: int) -> int:
        if mask == self.all_mask:
            return 0
        return (mask & -mask).bit_length()  # lowest set bit, 1-based

    # --- dwm's view() and toggleview() -------------------------------------------

    def view(self, mask: int) -> None:
        """Show exactly the tags in `mask`. mask == 0 flips back to the previous view."""
        mask &= self.all_mask
        if mask and mask == self.tagset:
            return
        self.sel ^= 1
        if mask:
            self.tagsets[self.sel] = mask
            self.prevtag = self.curtag
            self.curtag = self._tag_index(mask)
        else:
            self.prevtag, self.curtag = self.curtag, self.prevtag

    def toggle_view(self, mask: int) -> None:
        """Add or remove tags from the current view, but never end up viewing nothing."""
        new = self.tagset ^ (mask & self.all_mask)
        if not new:
            return
        self.tagsets[self.sel] = new
        if new == self.all_mask:
            self.prevtag, self.curtag = self.curtag, 0
        elif self.curtag and not new & (1 << (self.curtag - 1)):
            self.prevtag = self.curtag
            self.curtag = self._tag_index(new)
