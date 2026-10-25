# pymenu

A port of suckless [dmenu](https://tools.suckless.org/dmenu/) to macOS, for shell scripts:

```sh
printf '%s\n' red green blue | pymenu -p 'colour:'            # prints the choice
dir=$(ls ~/Projects | pymenu -i -l 10) || exit 1               # exit status 1: cancelled
name=$(echo | pymenu -p 'name:')                               # no items: a plain text prompt
```

The contract is dmenu's: **items on stdin** (one per line), **the choice on stdout**, **exit 0 = chosen,
exit 1 = cancelled**. If nothing matches, Return prints what you typed; Shift+Return always does.

It is a separate package: `src/pymenu/` imports nothing from `pywm`, and has its own script (`uv run pymenu`).

## Your job: the program itself

The command line, settings and glue are written (`cli.py`, `config.py`, `app.py`, with passing tests).
**You implement five steps.** Each one has a stub that fails loudly, a docstring that is the spec, and tests:

| Step | File | What | dmenu.c to read | Check with |
| ---- | ---- | ---- | --------------- | ---------- |
| 1 | `match.py` | which items match, in which order (pure function) | `match()` | `uv run pytest tests/test_pymenu_match.py` |
| 2 | `menu.py` | the state: text, cursor, selection, paging (2a text, 2b list, 2c finish) | `insert`, `movewordedge`, `calcoffsets`, parts of `keypress` | `tests/test_pymenu_menu.py` |
| 3 | `keys.py` | key press to Menu method: dmenu's big `switch` as a table | `keypress()` | `tests/test_pymenu_keys.py` |
| 4 | `macos/view.py` | drawing: prompt, input and cursor, items | `drawmenu()`, `drw.c` | by eye, step 5 |
| 5 | `macos/window.py` | the panel, key events, event loop, exit status | `setup()`, `run()` | `echo -e 'a\nb' \| uv run pymenu` |

Steps 1 to 3 are pure Python with no window: the tests *are* the spec, so work until they are green.
Do them in order (2 uses 1; 3 uses 2). Steps 4 and 5 are AppKit, and you see the result on screen.
The original source is at <https://git.suckless.org/dmenu/file/dmenu.c.html>; it is about 800 lines.

## Things worth knowing before step 5

* **No permissions needed.** pymenu receives keys in *its own* window. Accessibility and Input Monitoring
  are for reaching into other apps; this does neither. (Don't port `XGrabKeyboard` with an event tap.)
* A borderless `NSPanel` only takes keys if a subclass overrides `canBecomeKeyWindow` to return `True`.
* The app must be activated, and that only works under a real `NSApplication.run()` loop:
  use `PyObjCTools.AppHelper.runEventLoop()`. Under `runConsoleEventLoop` macOS says your process is
  frontmost but the window never becomes key (this was found the hard way in pywm).
* `NSApplicationMain` ends the process with a C `exit()`, which skips Python's stdout flush. Print with
  `flush=True` (`cli.emit` already does) and call `emit` *before* stopping the loop.
* AppKit's y axis points up. `NSView.isFlipped` returning `True` gives you a top-left origin inside a view.
* Use the *accessory* activation policy so there is no Dock icon.
* `src/pywm/bar/view.py` in this repository is a small working example of drawing text cells.

## Stretch goals

Horizontal paging by pixel width (dmenu's `calcoffsets` measures text; `Menu.per_page` is a fixed count),
`-m` and `-b` placement, Ctrl+Return multi-select, dead keys and input methods (`NSTextInputClient`,
dmenu's XIM), a `pymenu_run` launcher (dmenu_run lists executables on `$PATH`, with a cache), and a key
binding in `pywm/config.py` that spawns it, as dwm does with `dmenu_run`.
