# pymenu

A port of suckless [dmenu](https://tools.suckless.org/dmenu/) to macOS, for shell scripts:

```sh
printf '%s\n' red green blue | pymenu -p 'colour:'           # prints the choice
dir=$(ls ~/Projects | pymenu -i -l 10) || exit 1               # exit status 1: cancelled
name=$(echo | pymenu -p 'name:')                               # no items: a plain text prompt
app=$(ls /Applications | pymenu -c -i -p 'run:')               # centred on the screen, like Rofi
```

The contract is dmenu's: **items on stdin** (one per line), **the choice on stdout**, **exit 0 = chosen,
exit 1 = cancelled**. If nothing matches, Return prints what you typed; Shift+Return always does.
Ctrl+Return prints the selection *without closing*, so a script can read several.

Run it with `uv run pymenu`. It is a separate package: `src/pymenu/` imports nothing from `pywm`.
It needs **no macOS permissions**: it receives keys in its *own* window.

## How it fits together

```
 stdin ──► cli.py ──► app.py ──► macos/window.py ──► your screen
 (items,   flags,     glue       the panel, the event loop, exit status
  flags)   settings                  │            ▲
                                     │ NSEvent    │ draws
                                     ▼            │
                        macos/events.py      macos/view.py
                        key code ─► KeyPress    Menu ─► pixels
                                     │
              ┌──────────────────────┴───────────────────────┐
              │   THE PURE CORE: no AppKit, no window, no I/O │
              │   keys.py   KeyPress ─► a Menu method         │
              │   menu.py   text, cursor, selection, pages    │
              │   match.py  which items match, best first     │
              └───────────────────────────────────────────────┘
```

Everything inside the box can be (and is) tested without a screen. Only the two files on the right
touch AppKit, and even they are mostly small functions.

## Reading order

| # | file | what it teaches | dmenu.c counterpart | tested by |
| - | ---- | --------------- | ------------------- | --------- |
| 1 | `match.py` | a pure function; the three-group ordering | `match()` | `test_pymenu_match.py` |
| 2 | `menu.py` | a state machine and its **invariants** | `insert`, `movewordedge`, `calcoffsets`, much of `keypress` | `test_pymenu_menu.py`, `test_pymenu_invariants.py` |
| 3 | `keys.py` | behaviour as *data*: tables instead of a giant `switch` | `keypress()` | `test_pymenu_keys.py` |
| 4 | `macos/events.py` | the seam between the OS and the pure core | (X11 key events) | `test_pymenu_events.py` |
| 5 | `macos/view.py` | drawing with AppKit | `drawmenu()`, `drw.c` | `test_pymenu_view.py` (draws into a bitmap) |
| 6 | `macos/window.py` | an app, a window, an event loop, an exit status | `setup()`, `run()` | `test_pymenu_window_gui.py` |
| - | `cli.py`, `config.py`, `app.py` | flags, defaults, glue | `main()`, `config.def.h` | `test_pymenu_cli.py` |

The original is at <https://git.suckless.org/dmenu/file/dmenu.c.html>; it is about 800 lines.

## Three levels of tests

```sh
uv run pytest tests/test_pymenu_*.py -q                         # pure + offscreen: fast, no windows
PYMENU_GUI_TESTS=1 uv run pytest tests/test_pymenu_window_gui.py -q   # real window; flashes on screen for ~10 s
```

* **Pure** (`match`, `menu`, `keys`, `events`, `cli`): plain asserts. `test_pymenu_invariants.py`
  applies thousands of random operations and checks four invariants after each one.
* **Offscreen** (`view`): the view is drawn into an in-memory bitmap and individual pixels are read back.
* **End to end** (`window_gui`): the genuine program in a child process, with key events delivered
  to the window, checking what it prints and its exit status. Opt-in because it takes focus.

## AppKit lessons in this code

* **An accessory app** (`setActivationPolicy_`): no Dock icon, no menu bar of its own.
* **A borderless window only takes keys if it says so**: `canBecomeKeyWindow` must return `True`.
* **A real `NSApplication.run()` loop is required** for activation and key focus. Lighter loops make
  macOS report the process as frontmost while the window never receives keys.
* **Taking the focus from another app**: `activateIgnoringOtherApps_(True)` is marked deprecated, yet it is
  the call that works when pymenu is started by a background app (say, a pywm hotkey) while a third app
  has the focus. The newer `activate()` only succeeds when the app that launched us is frontmost, and
  otherwise silently does nothing. Measured on macOS 27; `_Session._warn_if_not_key` prints a warning
  to stderr if a future macOS ever disagrees.
* **Stopping `run()` from inside**: `app.stop_(None)` plus a posted dummy event. Terminating through
  AppKit would end the process with a C `exit()`, which skips Python's stdout flush and loses the exit status.
* **Views draw in `drawRect_`**; `isFlipped` gives a top-left origin; `NSRectClip` keeps a long item
  inside its cell; clipping state is bracketed by `saveGraphicsState` / `restoreGraphicsState`.
* **Colour spaces**: colours are specified in sRGB, but a bitmap is "Generic RGB", so `0x222222` reads
  back as 26 there. Convert before comparing (see `tests/test_pymenu_view.py`).
* **A subclass method with underscores in its name** is read by PyObjC as an Objective-C selector
  with arguments, so helpers live in plain module-level functions.
* **stdout is the API.** Never `print` for debugging inside the program; use stderr.

## How it differs from dmenu

* `-w` (embedding in another window) is accepted and ignored: there is no such thing on macOS.
* `-f` (grab the keyboard before reading stdin) is accepted and does nothing.
* A horizontal page holds a **fixed** number of items, sized from the widest ones, where dmenu re-measures
  to fit as many as possible. This keeps `Menu` simple: `per_page` is one number.
* Cmd+V pastes (dmenu's Ctrl+y still works). Clicking elsewhere cancels the menu.
* The menu covers the full width of the screen the mouse is on (or `-m N`), at the top (or bottom with `-b`).
* `-c` centres it instead, as dmenu's centre patch and Rofi do: `-W POINTS` wide (default 700, never more
  than 90% of the screen), in the middle of the screen both ways. Unless you give `-l`, `-c` shows a
  vertical list of 10 lines, since a centred one-line strip looks odd. `menu_rect` in `macos/window.py`
  is the only place that knows about it. The window's width is decided *before* the view is built,
  because the view draws at that width and the horizontal page size is fitted to it.

## Things to try next

* **Horizontal paging by pixel width**, like `calcoffsets`: make pages hold different numbers of items.
  Which `Menu` methods assume a fixed `per_page`, and what would have to change?
* **Unicode**: type `å` and match an item stored as `a` + a combining ring (`blåbær`). Where is the
  right place to normalise (`unicodedata.normalize`)?
* **Dead keys and input methods** (Norwegian layouts!): `NSTextInputClient`, dmenu's XIM equivalent.
* **`pymenu_run`**: dmenu_run lists executables on `$PATH` (with a cache) and runs the choice.
* **Bind it in pywm**: `Key(MOD, "p", WM.spawn, ("pymenu_run",))` in `src/pywm/config.py`, the way dwm
  spawns dmenu.
* **Mouse support**: click an item to choose it.
