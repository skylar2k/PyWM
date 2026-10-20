# Architecture

A window manager is a small problem inside a hostile environment. The *small problem*: given windows, tags
and a layout, decide where each window goes. The *hostile environment*: an OS that is asynchronous,
permission-gated and sometimes wrong. pywm's structure keeps the two apart.

```
 macOS                                                              macOS
   │  AX notifications, NSWorkspace, key presses                      ▲  AX calls (move, resize, focus)
   ▼                                                                  │
┌──────────────────────────── platform/macos ───────────────────────────┐
│ observers  workspace  hotkeys                  ax  parking             │  ADAPTER
└───────────────┬──────────────────────────────────────▲────────────────┘  (knows macOS)
                │ Event                                │ set_frame / hide / focus ...
                ▼                                      │
┌────────────────────────────── controller.py ─────────┴────────────────┐
│ debounce, re-read the world, send only differences, read back what     │  SHELL
│ apps really did, retry                                                 │
└───────────────┬──────────────────────────────────────▲────────────────┘
                │ sync_app(), window_focused(),        │ Plan
                │ key actions                          │
                ▼                                      │
┌────────────────────────────────── core/ ───────────────────────────────┐
│ WindowManager: windows, monitors, tags, layouts. No I/O at all.        │  CORE
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ wm.changed  (Observer)
                               ▼
                        bar/  (status bar)
```

## The layers

**Core (`core/`, `geometry.py`)** is pure. `WindowManager` is a state machine: you call methods (`sync_app`,
`view`, `zoom`...) and it updates its model. `flush()` returns a **`Plan`**: what the world *should* look like
(`Show(rect)` / `Hide()` per window, which window to focus, which actions to run). It never *does* anything.
So a dwm behaviour can be tested in three lines with no display (`tests/test_wm.py`).

**Shell (`controller.py`)** owns the mess:
* *Debouncing.* One app opening fires a burst of notifications; `resync_soon` collapses them.
* *Level-triggered sync.* Notifications are only hints ("something changed in pid 123"). The controller asks for
  a fresh snapshot and the core diffs it against its model (`sync_app`), so lost, duplicated or reordered
  notifications are harmless.
* *Read-back.* After `set_frame` the adapter reports the frame the app *actually* got. If an app refused to be
  small, the core `learn_size()`s its minimum and a second planning pass fits it.
* *Idempotence.* It remembers the last placement per window and sends only differences.

**Adapter (`platform/`)**: `Platform` is a `typing.Protocol` with ~15 methods. `MacOSPlatform` implements it with
AX/CoreGraphics/AppKit. The tests' `FakePlatform` implements it with a dict. The controller cannot tell them apart.

**Bar (`bar/`)** is a subscriber to `wm.changed`. The WM does not import it; it does not call into the WM. It
receives immutable `MonitorStatus` values and paints them.

**Config (`config.py`)** is the one file you edit. It imports the same types the program uses (`Key`, `Rule`,
`WM`) and is passed to the parts that need settings, like a `config.h` included by `dwm.c`.

## dwm to pywm

| dwm (C)                    | pywm                                          |
| -------------------------- | --------------------------------------------- |
| `Client`                   | `core/types.py: Window`; `tags` is a bitmask  |
| `Monitor`                  | `core/monitor.py: Monitor`; two tagsets so `view(0)` flips back |
| `Monitor.clients`          | `Monitor.order`: tiling order, `[0]` is master |
| `Monitor.stack`            | `Monitor.stack`: focus history, `[0]` is latest |
| `pertag` patch             | `Monitor.pertag`: each tag keeps its layout, `nmaster`, `mfact` |
| `Layout{symbol, arrange}`  | `core/layouts.py: Layout`; `arrange` is a plain function |
| `rules[]`, `keys[]`        | `config.RULES`, `config.KEYS`                  |
| handlers (`view`, `zoom`)  | `WindowManager` methods                        |
| `arrange()`                | `WindowManager.flush()`, which returns a `Plan` |
| status bar                 | `bar/`                                          |

Where macOS forced a different design:
* **Tags are virtual.** X11 can unmap a window; macOS cannot hide one. Hidden windows are *parked* in the
  bottom-right corner (`parking.py`) and restored when their tag is shown.
* **Fullscreen, minimized and other-Space windows are suspended** (`Window.suspended`): they keep their tags but
  layouts and focus skip them.
* **Dialogs and palettes float** (they follow tags but are never resized); other window kinds are ignored.

## Patterns, and the book chapters behind them

| Pattern | Where | Read |
| ------- | ----- | ---- |
| **Strategy** | `core/layouts.py`: a layout is a function chosen by name | *Software Design for Python Programmers* ch. 8 (Template Method and Strategy); *Fluent Python* ch. 10 (Design Patterns with First-Class Functions) |
| **Adapter / Facade** | `platform/`: 15 methods hide three C APIs | *Software Design* ch. 10 (Adapter and Façade), esp. 10.3 "Choosing between Adapter and Façade" |
| **Observer** | `core/events.py: Signal`, subscribed to by `bar/` | *Software Design* ch. 12 |
| **Command as a function** | `Key(mods, key, WM.view, 3)`: no class, just a callable and arguments | *Fluent Python* ch. 10, "The Command Pattern" |
| **State machine** | `WindowManager`, `Monitor.view()` | *Software Design* ch. 13 (State) |
| **Protocol** | `platform/__init__.py` | *Fluent Python* ch. 13, "Static Protocols" |
| **Immutable values** | `Rect`, `WindowInfo`, `Plan`, `MonitorStatus` | *Fluent Python* ch. 5 (Data Class Builders) |
| **Functional core, imperative shell** | `core/` vs `controller.py` | the idea that makes the rest cheap to test |

Also worth reading: *Fluent Python* ch. 18 (`match`, used for events and placements), ch. 19-21 (concurrency;
pywm is deliberately single-threaded on one run loop, so the core needs no locks).

## Python features worth noticing

* `@dataclass(frozen=True, slots=True)` for values; plain `@dataclass(slots=True)` for the mutable `Window`/`Monitor`.
* `match` with class patterns (`case Show(rect=None)`) in `controller.py` and `types.classify`.
* PEP 695 syntax: `class Signal[**P]` and `type` aliases.
* `IntFlag` for modifier keys (`Mod.ALT | Mod.SHIFT`).
* `typing.Protocol` for the OS boundary: structural typing, no inheritance.
