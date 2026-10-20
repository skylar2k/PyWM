"""A thin, Pythonic layer over the Accessibility (AX) C API.

PyObjC exposes the raw functions, which return `(error_code, value)` tuples. This
module turns error codes into exceptions or `None` and converts AXValue structs
to our own `Rect`, so the rest of the adapter reads like ordinary Python.

Two failure modes matter more than all others:

* ``kAXErrorCannotComplete``: the app did not answer within the messaging
  timeout. A hung app must never freeze the window manager, so we turn it into
  `AXUnresponsive`, and callers back off from that app for a while.
* "no value / unsupported": perfectly normal (a window with no title, say), so
  those become `None`.
"""

import ctypes
from typing import Any

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementCreateSystemWide,
    AXUIElementGetPid,
    AXUIElementIsAttributeSettable,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXUIElementSetMessagingTimeout,
    AXValueCreate,
    AXValueGetValue,
    kAXErrorActionUnsupported,
    kAXErrorAttributeUnsupported,
    kAXErrorCannotComplete,
    kAXErrorInvalidUIElement,
    kAXErrorNotImplemented,
    kAXErrorNoValue,
    kAXErrorSuccess,
    kAXValueTypeCGPoint,
    kAXValueTypeCGSize,
)
from Quartz import CGPoint, CGSize

from pywm.geometry import Rect

# Attribute names that PyObjC has no constant for.
FULLSCREEN = "AXFullScreen"


class AXFailure(Exception):
    def __init__(self, code: int, what: str) -> None:
        super().__init__(f"AX error {code} during {what}")
        self.code = code


class AXUnresponsive(AXFailure):
    """The target app did not answer in time."""


_BENIGN = {
    kAXErrorNoValue,
    kAXErrorAttributeUnsupported,
    kAXErrorActionUnsupported,
    kAXErrorNotImplemented,
    kAXErrorInvalidUIElement,
}


def _check(err: int, what: str) -> bool:
    """True on success, False on a benign 'nothing there', raises otherwise."""
    if err == kAXErrorSuccess:
        return True
    if err == kAXErrorCannotComplete:
        raise AXUnresponsive(err, what)
    if err in _BENIGN:
        return False
    raise AXFailure(err, what)


# --- elements -----------------------------------------------------------------------


def system_wide() -> Any:
    return AXUIElementCreateSystemWide()


def application(pid: int, timeout: float) -> Any:
    el = AXUIElementCreateApplication(pid)
    AXUIElementSetMessagingTimeout(el, timeout)
    return el


def set_global_timeout(seconds: float) -> None:
    """Bound every AX call in this process. Without it one frozen app blocks us for ~6s per call."""
    AXUIElementSetMessagingTimeout(system_wide(), seconds)


def pid_of(el: Any) -> int | None:
    err, pid = AXUIElementGetPid(el, None)
    return pid if err == kAXErrorSuccess else None


# --- attributes ---------------------------------------------------------------------


def get(el: Any, attr: str) -> Any | None:
    err, value = AXUIElementCopyAttributeValue(el, attr, None)
    return value if _check(err, f"get {attr}") else None


def set_(el: Any, attr: str, value: Any) -> bool:
    return _check(AXUIElementSetAttributeValue(el, attr, value), f"set {attr}")


def is_settable(el: Any, attr: str) -> bool:
    err, settable = AXUIElementIsAttributeSettable(el, attr, None)
    return bool(settable) if _check(err, f"settable {attr}") else False


def perform(el: Any, action: str) -> bool:
    return _check(AXUIElementPerformAction(el, action), f"perform {action}")


# --- geometry -----------------------------------------------------------------------


def position(el: Any) -> tuple[int, int] | None:
    value = get(el, "AXPosition")
    if value is None:
        return None
    ok, pt = AXValueGetValue(value, kAXValueTypeCGPoint, None)
    return (round(pt.x), round(pt.y)) if ok else None


def size(el: Any) -> tuple[int, int] | None:
    value = get(el, "AXSize")
    if value is None:
        return None
    ok, sz = AXValueGetValue(value, kAXValueTypeCGSize, None)
    return (round(sz.width), round(sz.height)) if ok else None


def frame(el: Any) -> Rect | None:
    pos, sz = position(el), size(el)
    return Rect(pos[0], pos[1], sz[0], sz[1]) if pos and sz else None


def set_position(el: Any, x: int, y: int) -> bool:
    return set_(el, "AXPosition", AXValueCreate(kAXValueTypeCGPoint, CGPoint(x, y)))


def set_size(el: Any, w: int, h: int) -> bool:
    return set_(el, "AXSize", AXValueCreate(kAXValueTypeCGSize, CGSize(w, h)))


# --- window identity ----------------------------------------------------------------

_hiservices = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
try:
    _get_window = _hiservices._AXUIElementGetWindow
    _get_window.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    _get_window.restype = ctypes.c_int32
except AttributeError:  # pragma: no cover - the symbol has existed for over a decade
    _get_window = None


def window_id(el: Any) -> int | None:
    """The CGWindowID of an AX window element.

    AX elements have no stable identity of their own, but CoreGraphics gives
    every window a number that lives as long as the window does. The function
    that links the two (`_AXUIElementGetWindow`) is private but has been used by
    every macOS tiling manager for years.
    """
    if _get_window is None:
        return None
    import objc

    out = ctypes.c_uint32(0)
    if _get_window(ctypes.c_void_p(objc.pyobjc_id(el)), ctypes.byref(out)) != 0:
        return None
    return out.value or None
