"""The composition root: the one place that knows about every part and plugs them together."""

import logging
import os
import sys
from pathlib import Path

from pywm import config
from pywm.controller import Controller
from pywm.core.wm import WindowManager
from pywm.platform.macos import permissions
from pywm.platform.macos.platform import MacOSPlatform

log = logging.getLogger("pywm")
LOG_FILE = Path("~/Library/Logs/pywm.log").expanduser()  # used when there is no terminal (pywm.app)

MISSING_PERMISSION = """\
pywm needs {what} permission.
macOS grants it to the app that launched pywm: pywm.app itself, or your terminal (Terminal,
iTerm2, Ghostty...) if you ran `uv run pywm`. Enable that app in
System Settings > Privacy & Security > {pane}, then start pywm again."""


def main() -> int:
    in_terminal = sys.stderr is not None and sys.stderr.isatty()
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("PYWM_DEBUG") else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        **({} if in_terminal else {"filename": LOG_FILE}),  # a bundled app has no visible stderr
    )
    if not permissions.ensure_accessibility():
        log.error(MISSING_PERMISSION.format(what="Accessibility", pane="Accessibility"))
        return 1
    if not permissions.ensure_input_monitoring():
        log.warning("Input Monitoring is not granted, so hotkeys will not work.")

    platform = MacOSPlatform(config)
    wm = WindowManager(config)
    controller = Controller(platform, wm, config.KEYS)

    bar = None
    if config.BAR_ENABLED:
        from pywm.bar import Bar

        bar = Bar(config)
        wm.changed.connect(bar.update)  # the bar is just a subscriber

    try:
        controller.start()  # blocks until you quit (Option+Shift+Q) or press Ctrl-C
    finally:
        controller.stop()  # always put hidden windows back
        if bar is not None:
            bar.close()
    return 0
