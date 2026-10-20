# 2. macOS notes: the traps, and how pywm handles each

Everything in this file is code you can find in `src/pywm/platform/macos/`.

## Window discovery (`observers.py`, `workspace.py`)

One `AXObserver` per running app. Which notification goes on which element matters:

| Element       | Notification                                   | Why there |
| ------------- | ---------------------------------------------- | --------- |
| application   | `kAXWindowCreatedNotification`                 | new windows |
| application   | `kAXFocusedWindowChangedNotification`          | focus moves within an app |
| each window   | `kAXUIElementDestroyedNotification`            | a window announces its *own* death, so you must already be subscribed to it |
| each window   | `kAXWindowMiniaturized/DeminiaturizedNotification` | minimized windows leave the layout |

`NSWorkspace` notifications tell us when to *create or drop* observers (launch / terminate), plus hide /
unhide, app activation (Cmd-Tab), and `ActiveSpaceDidChange`, which also fires when a window enters or
leaves native fullscreen. Newly launched apps are often not AX-ready, so `Controller.handle(AppLaunched)`
re-syncs at +0.15 s, +0.5 s and +1.5 s.

On startup `Controller.start()` enumerates existing windows before the event loop begins.

**Window identity.** AX elements have no stable ID. `_AXUIElementGetWindow` (private, used by yabai,
AeroSpace and Rectangle for years) returns the CoreGraphics window number, which is stable for the window's
life. See `ax.window_id`.

## What gets managed (`core/types.py: classify`)

| AX subrole                                  | Role      |
| ------------------------------------------- | --------- |
| `AXStandardWindow`                          | tiled     |
| `AXDialog`, `AXSystemDialog`, `AXFloatingWindow` (palettes) | floating: tags and hiding apply, never resized |
| anything else                               | ignored   |

Also: windows whose `AXSize` is not settable float. Native fullscreen (`AXFullScreen`), minimized, and
other-Space windows are *suspended*. Override per app with a `Rule(...)` in `config.RULES`.

## Hotkeys (`hotkeys.py`, `keycodes.py`)

A `CGEventTap` sees every key before apps do; returning `None` swallows it. Details that bite:

* Needs **Accessibility** (to swallow) *and* **Input Monitoring** (to see keys).
* The callback must be fast, so it only looks the chord up and queues the work with `AppHelper.callAfter`.
* macOS disables taps that are slow; we re-enable on `kCGEventTapDisabledByTimeout`.
* We also swallow the matching key-*up*, otherwise apps see an orphan key-up.
* Flags include caps-lock/fn bits; we mask to shift/ctrl/option/cmd before comparing.
* Chords use **physical key codes**, not characters, because Option rewrites characters (Option+J types
  ∆). Letters, digits, return, space and tab sit in the same place on US and Nordic layouts; punctuation
  such as `comma`/`period` is by *position*.
* Option is the dwm-style `mod`, but it is also how many layouts type `@ { [ |`. If that hurts, set
  `MOD = Mod.CTRL | Mod.ALT` in `config.py`.

## Coordinates (`geometry.py`, `screens.py`)

AX and CoreGraphics: origin **top-left** of the primary display, y down. AppKit: origin **bottom-left**
of the primary display, y up. pywm works in AX coordinates internally. `geometry.flip_y` is the single
conversion, used only for `NSScreen.visibleFrame` (and for placing the bar panel, which *is* an AppKit window).

**Where displays come from.** `NSScreen` can go stale in a process with no running `NSApplication`, so geometry is
read from CoreGraphics every time (`CGGetActiveDisplayList` + `CGDisplayBounds`). AppKit is used only for the
display *name* and the *usable area* (`visibleFrame`, which excludes the menu bar and Dock); if AppKit's rectangle is
missing or not inside its display we use the full frame. See `screens.read_screens`.

**Notched displays.** `visibleFrame` excludes `NSScreen.safeAreaInsets.top` (38 pt on a MacBook with a notch)
*even when the menu bar auto-hides*, so the work area never starts at y=0 there. This is not staleness: it is the same with
and without an `NSApplication`.

**The bar draws over that band.** A borderless panel at window level 25 (menu bar: 24) is not constrained by AppKit, so it can
sit at y=0 (verified by placing one there). `Monitor.bar_rect` is the band: the very top of the display, at least as tall as the
reserved area, so the menu bar never peeks out underneath. Tiled windows start below the band, so covering it costs no space.
The bar package draws only a compact indicator inside the band (the tags and the layout symbol, no window title),
starting at the right edge of the notch (`NSScreen.auxiliaryTopRightArea`) so the app menus on the left stay reachable and
the rounded screen corners are not involved. On a display with no notch it starts at the horizontal centre. While auto-hide
shows the menu bar, the indicator stays on top of it.

Caveat: `visibleFrame` can still lag behind a Dock-size or auto-hide change that does not alter the display
list; pywm re-reads screens on every `ScreensChanged` event (display changes and Space changes), not continuously.

## Apps that refuse to resize

Some windows have a minimum (or maximum) size. The flow:

1. `Controller._execute` calls `platform.set_frame(id, rect)`, which sets size → position → size and **returns the
   frame read back from the app**.
2. If the size differs, `WindowManager.learn_size` records `min_size`/`max_size` on the `Window`.
3. If that was new information it returns `True`, and the controller plans a second time. `layouts.fit` grows the
   slot to the minimum, then slides it back so it stays inside the work area. It may overlap a neighbour,
   which is what dwm does too.

Two passes at most, so a window that lies about its size cannot cause an infinite loop.

## Hung apps (`platform.py`, `ax.py`)

AX calls are synchronous and block until the target app answers (default timeout ~6 s). pywm:

* calls `AXUIElementSetMessagingTimeout` on the system-wide element and on every app element
  (`ax_timeout`, default 0.3 s);
* turns `kAXErrorCannotComplete` into `AXUnresponsive`;
* **backs off** that pid for 2 s (`_back_off`), returns `None` from `window_infos`, and schedules a re-check;
* `Controller.resync` treats `None` as "unknown", **not** "no windows", so a hung app never has its windows forgotten.

## Hiding windows (`parking.py`)

No per-window hide API exists. pywm moves windows to the bottom-right corner of the combined desktop and records their
real frames in memory. They are restored on tag view and on every exit path (including SIGINT/SIGTERM/SIGHUP).
After a hard crash they sit in the corner, but the next start adopts every window it can see and tiles it back.

## Spaces

AX only lists windows on the **current** Space. A window that "disappears" from `AXWindows` may be on another Space, or
closed. `Platform.window_exists` asks CoreGraphics (`CGWindowListCopyWindowInfo(kCGWindowListOptionAll)`) to tell them
apart; windows still alive elsewhere become `away` (suspended) rather than forgotten, so they keep their tags. Using a
single Space plus native fullscreen is the best-supported setup.

## Focus (`platform.focus`)

`NSRunningApplication.activate` is restricted since macOS 14 (cooperative activation). pywm uses plain AX instead:
set `AXFrontmost` on the app, `AXMain` and `AXFocusedWindow`, then perform `AXRaise` on the window.

## Event loop and shutdown

`AppHelper.runConsoleEventLoop` runs the main run loop; observers and the event tap are attached to it in common modes.
SIGINT, SIGTERM and SIGHUP all stop the loop, after which `Controller.stop()` runs `restore_all()`.
`SIGKILL` cannot be caught; just start pywm again.

## What is *not* handled (yet)

Exercises in disguise (see the README):

* mouse: focus-follows-mouse, Mod+drag to move/resize floating windows
* snapping a tiled window back after the user drags it
* window animations; focus-border overlay; clickable tags in the bar
* per-Space management (needs private SkyLight APIs)
* layout-aware keys (`UCKeyTranslate`) for non-QWERTY punctuation
