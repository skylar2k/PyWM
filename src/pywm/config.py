"""pywm's configuration. Edit this file and restart pywm, exactly as you would edit dwm's config.h.

Nothing here is parsed or validated by a loader: it is ordinary Python. A mistake is an
ordinary traceback at startup. The names below (`WM.view`, `Rule`, `Key`, ...) are the same
types the rest of the program uses, so you can see in one place how settings reach the code.
"""

from pywm.core.keys import Key, Mod
from pywm.core.rules import Rule
from pywm.core.wm import WindowManager as WM

# --- appearance -----------------------------------------------------------------------

GAP = 6  # pixels between windows, and between windows and the screen edge
BAR_ENABLED = True
BAR_FONT_SIZE = 13
COLORS = {  # dwm's defaults, as 0xRRGGBB
    "norm_fg": 0xBBBBBB,
    "norm_bg": 0x222222,
    "sel_fg": 0xEEEEEE,
    "sel_bg": 0x005577,
}

# --- layout ---------------------------------------------------------------------------

TAGS = ("1", "2", "3", "4", "5", "6", "7", "8", "9")  # 1 to 9 names, shown in the bar
LAYOUT = "tile"  # initial layout: "tile", "float", "monocle" or "bstack" (see core/layouts.py)
MFACT = 0.55  # share of the width given to the master column
NMASTER = 1  # windows in the master column
NEW_AT_MASTER = True  # new windows become master (dwm's default); False puts them at the end
FOLLOW_FOCUS = True  # Cmd-Tab to a window on a hidden tag switches to that tag

# --- behaviour ------------------------------------------------------------------------

TERMINAL = ("open", "-na", "Ghostty")  # what Mod+Shift+Return runs
AX_TIMEOUT = 0.3  # seconds to wait on one app before giving up on it (hung apps)

# --- rules (dwm's rules[]) ------------------------------------------------------------
# The first rule whose fields all match wins. `app` and `title` are regular expressions;
# `app` is searched in the app's name *and* its bundle id.

RULES = [
    Rule(app=r"^(System Settings|System Preferences)$", floating=True),
    Rule(app=r"^(Calculator|Archive Utility|Digital Color Meter)$", floating=True),
    Rule(app=r"^(Installer|Software Update)$", floating=True),
    # Rule(app="Slack", tag=3),            # open Slack on tag 3
    # Rule(app="Ice", ignore=True),        # never touch this app's windows
]

# --- key bindings ---------------------------------------------------------------------
# Key(modifiers, key, function, argument...) calls function(wm, argument...).
# The main modifier is Option. It also types symbols on many layouts (@ { [ | on Nordic ones),
# and a bound combination no longer types them. Mod.CTRL | Mod.ALT is a common alternative.

MOD = Mod.R_ALT
SHIFT, CTRL = Mod.SHIFT, Mod.CTRL

KEYS = [
    Key(MOD | SHIFT, "return", WM.spawn, TERMINAL),
    Key(MOD, "j", WM.focus_stack, +1),
    Key(MOD, "k", WM.focus_stack, -1),
    Key(MOD, "i", WM.inc_nmaster, +1),
    Key(MOD, "d", WM.inc_nmaster, -1),
    Key(MOD, "h", WM.set_mfact, -0.05),
    Key(MOD, "l", WM.set_mfact, +0.05),
    Key(MOD, "return", WM.zoom),
    Key(MOD, "tab", WM.view_previous),
    Key(MOD | SHIFT, "c", WM.kill),
    Key(MOD, "t", WM.set_layout, "tile"),
    Key(MOD, "f", WM.set_layout, "float"),
    Key(MOD, "m", WM.set_layout, "monocle"),
    Key(MOD, "u", WM.set_layout, "bstack"),
    Key(MOD, "space", WM.toggle_layout),
    Key(MOD | SHIFT, "space", WM.toggle_floating),
    Key(MOD, "b", WM.toggle_bar),
    Key(MOD, "0", WM.view, 0),  # tag 0 means "all tags"
    Key(MOD | SHIFT, "0", WM.tag, 0),
    Key(MOD, "comma", WM.focus_monitor, -1),
    Key(MOD, "period", WM.focus_monitor, +1),
    Key(MOD | SHIFT, "comma", WM.tag_monitor, -1),
    Key(MOD | SHIFT, "period", WM.tag_monitor, +1),
    Key(MOD | SHIFT, "q", WM.quit),
]

# dwm's TAGKEYS macro: four bindings per tag.
for n in range(1, len(TAGS) + 1):
    KEYS += [
        Key(MOD, str(n), WM.view, n),
        Key(MOD | CTRL, str(n), WM.toggle_view, n),
        Key(MOD | SHIFT, str(n), WM.tag, n),
        Key(MOD | CTRL | SHIFT, str(n), WM.toggle_tag, n),
    ]
