"""The vocabulary shared by the core and the platform adapters."""

from dataclasses import dataclass
from enum import StrEnum

from pywm.geometry import Rect

type WindowId = int
type Size = tuple[int, int]

UNBOUNDED = 1 << 20  # stands in for 'no maximum' in a Size


class Role(StrEnum):
    """What the WM should do with a window, decided from its AX subrole."""

    TILED = "tiled"  # AXStandardWindow: takes part in layouts
    FLOATING = "floating"  # dialogs and palettes: managed (tags, hiding) but never tiled
    IGNORED = "ignored"  # anything else: we pretend it does not exist


# Subroles are the strings the Accessibility API reports for kAXSubroleAttribute.
_FLOATING_SUBROLES = frozenset({"AXDialog", "AXSystemDialog", "AXFloatingWindow"})


def classify(subrole: str | None) -> Role:
    match subrole:
        case "AXStandardWindow":
            return Role.TILED
        case s if s in _FLOATING_SUBROLES:
            return Role.FLOATING
        case _:
            return Role.IGNORED


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """An immutable *snapshot* of a window as the OS currently reports it."""

    id: WindowId
    pid: int
    app: str
    bundle_id: str
    title: str
    subrole: str | None
    frame: Rect
    minimized: bool = False
    fullscreen: bool = False  # native macOS fullscreen: we leave these alone
    resizable: bool = True
    away: bool = False  # on another Space, or its app is hidden


@dataclass(slots=True)
class Window:
    """The WM's own mutable record of a window it manages."""

    id: WindowId
    pid: int
    app: str
    bundle_id: str
    title: str
    frame: Rect
    tags: int  # bitmask: bit 0 is tag 1
    monitor: int  # Monitor.id
    floating: bool
    min_size: Size | None = None  # learned by watching what the app actually did
    max_size: Size | None = None
    minimized: bool = False
    fullscreen: bool = False
    away: bool = False

    @property
    def suspended(self) -> bool:
        """Suspended windows keep their tags but are skipped by layouts and focus."""
        return self.minimized or self.fullscreen or self.away


@dataclass(frozen=True, slots=True)
class Screen:
    """A display, as reported by the platform. `work_area` excludes menu bar and Dock."""

    id: int
    name: str
    frame: Rect
    work_area: Rect


# --- the WM's output: a Plan describing what the outside world should do ---------------


@dataclass(frozen=True, slots=True)
class Show:
    """Make the window visible. `rect=None` means 'where it already is' (floating windows)."""

    rect: Rect | None


@dataclass(frozen=True, slots=True)
class Hide:
    """Move the window out of sight (macOS has no real 'hide one window' API)."""


type Placement = Show | Hide


@dataclass(frozen=True, slots=True)
class Close:
    window: WindowId


@dataclass(frozen=True, slots=True)
class Spawn:
    argv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Quit:
    pass


type Action = Close | Spawn | Quit


@dataclass(frozen=True, slots=True)
class Plan:
    """Everything the shell has to do to make the world match the model."""

    placements: dict[WindowId, Placement]
    focus: WindowId | None = None
    raise_order: tuple[WindowId, ...] = ()  # raise these in order; the last ends up on top
    actions: tuple[Action, ...] = ()
