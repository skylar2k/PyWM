"""pywm's status bar, as a self-contained package.

Using it takes two lines (see `pywm/app.py`):

    bar = Bar(config)
    wm.changed.connect(bar.update)

The window manager does not import this package, and this package never calls back into the
window manager. All it receives is a list of `MonitorStatus` values: the Observer pattern.
To replace the bar (a menu-bar item, a tmux line...), write another subscriber.

    bar/bar.py    one panel per monitor, kept in sync with the WM's status
    bar/view.py   the drawing
"""

from pywm.bar.bar import Bar

__all__ = ["Bar"]
