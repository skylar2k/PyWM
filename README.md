# pywm

A port of [dwm](https://dwm.suckless.org/) to macOS in Python 3.15, small enough to read in an evening
and structured so you can grow it.

```
Option+Shift+Return  new terminal        Option+j / k    focus next / previous
Option+Return        make master         Option+h / l    shrink / grow master
Option+1..9          view tag            Option+Shift+1..9  move window to tag
Option+t / m / f / u tile / monocle / float / bottom-stack
Option+Shift+q       quit
```

## Run it

```bash
uv sync
uv run pywm
uv run pytest        # no screen or permissions needed
```

pywm needs two permissions, granted to the app that launches it (Terminal, iTerm2, Ghostty...) under
*System Settings > Privacy & Security*: **Accessibility** (move other apps' windows) and
**Input Monitoring** (see your hotkeys). `PYWM_DEBUG=1 uv run pywm` prints what it is doing.

If pywm is killed with `kill -9`, hidden windows sit in the bottom-right corner; just start pywm again and it
tiles them back. Any normal exit (Option+Shift+Q, Ctrl-C, `kill`) puts them back itself.

## Run it as an app

A real `pywm.app` gets its own permissions (instead of borrowing your terminal's), needs no terminal window,
and has no Dock icon. It is built with [py2app](https://py2app.readthedocs.io/) in *alias mode*: a genuine app
bundle whose launcher points back at this checkout and its `.venv`.

```bash
uv sync --group build
cd packaging && uv run python setup.py py2app -A && cd ..
open packaging/dist/pywm.app
```

1. The first launch asks for **Accessibility**: enable *pywm* under *System Settings > Privacy & Security*,
   also add it under **Input Monitoring**, then `open` the app again.
2. Quit with Option+Shift+Q (there is no terminal to Ctrl-C), or `pkill -f pywm`.
3. Logs go to `~/Library/Logs/pywm.log`; `PYWM_DEBUG=1` still works when run from a terminal.
4. To start at login: *System Settings > General > Login Items*, add `pywm.app`.

Editing `src/pywm/config.py` takes effect on the next launch: **no rebuild**. Rebuild only when something in
`packaging/` changes. A rebuild re-signs the app, so macOS may forget its permissions; if so, remove *pywm* from
both Privacy lists and add it again. Do not run the terminal copy and the app at the same time.

The app only knows about the bundler through `packaging/pywm_app.py`, a 3-line script that calls `pywm.app:main`.
py2app releases lag new Python versions, so if a future Python breaks it, only `packaging/` has to change
(PyInstaller is the fallback; it freezes the config, so you would rebuild after each edit, much as dwm
recompiles).

## Configure it: edit `src/pywm/config.py`

Like dwm's `config.h`, the config is a source file you edit and restart. It is ordinary Python: gaps,
tags, layout, window rules and the key table.

```python
Key(MOD | SHIFT, "return", WM.spawn, TERMINAL)  # Option+Shift+Return runs TERMINAL
Key(MOD, "j", WM.focus_stack, +1)  # Option+j calls WM.focus_stack(wm, +1)
Rule(app="Slack", tag=3)  # open Slack on tag 3
```

Option also types symbols on many layouts (`@ { [ |` on Nordic ones), and a bound combination stops typing
them. Change `MOD` to `Mod.CTRL | Mod.ALT` if that bites.

## Where things are

```
src/pywm/
  config.py            YOU EDIT THIS: settings, rules, keys
  app.py               plugs the parts together and starts them
  controller.py        the "shell": OS events in, Plan out, read back what apps did
  geometry.py          Rect, and the single y-axis flip
  core/                PURE PYTHON: no macOS, tested without a screen
    wm.py                WindowManager: windows, monitors, tags (dwm's brain)
    monitor.py           tagsets, per-tag layout settings, view()/toggle_view()
    layouts.py           tile / bstack / monocle / float as pure functions
    types.py  keys.py  rules.py  events.py
  platform/
    __init__.py          the Platform Protocol: the only door to the OS
    macos/               the only code that touches macOS
      ax.py                the Accessibility API, wrapped
      observers.py         one AXObserver per app
      workspace.py         app launch/quit, Space and display changes
      hotkeys.py           global hotkeys (CGEventTap)
      screens.py           displays, from CoreGraphics
      parking.py           how hidden windows are hidden
      platform.py          the Platform implementation
  bar/                 the status bar, a self-contained package
    bar.py               one panel per monitor
    view.py              the drawing
tests/                 165 tests; fake_platform.py stands in for macOS
docs/
  architecture.md      the layers, dwm-to-pywm map, patterns and the book chapters behind them
  macos-notes.md       every macOS trap this code works around, and how
```

Read in this order: `config.py`, `core/wm.py`, `controller.py`, then `docs/architecture.md`.

## Extending it

**A key:** add a `Key(...)` line to `KEYS` in `config.py`. Any `WindowManager` method works as the function.

**A window rule:** add a `Rule(...)` to `RULES`; the first match wins.

**A layout:** write a function `(area, n, nmaster, mfact) -> list[Rect]` in `core/layouts.py` and add a
`Layout(...)` to `LAYOUTS`. Gaps, tags and minimum sizes all work around it automatically. For example:

```python
def grid(area, n, nmaster, mfact):
    cols = math.ceil(math.sqrt(n)) if n else 1
    rows = math.ceil(n / cols) if n else 1
    w, h = area.w // cols, area.h // rows
    return [Rect(area.x + i % cols * w, area.y + i // cols * h, w, h) for i in range(n)]
```

**An action:** add a method to `WindowManager` that changes state (it must not do I/O), then bind it with `Key`.

**Something that reacts to changes** (a different bar, a log): `wm.changed.connect(fn)`; `fn` receives a list
of `MonitorStatus`. See `app.py` and `bar/`.

**Ideas to try, easiest first:** a `cycle_layout` action; a `focus_last` action (the second entry in
`Monitor.stack`); a `sticky` rule that puts a window on every tag; centring floating dialogs; snapping a
tiled window back after you drag it; focus-follows-mouse; a focus-border overlay; a second kind of
`Platform` (say X11) to prove the boundary holds.
