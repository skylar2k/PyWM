"""config.py is plain Python, so these tests guard against typos in the *data*."""

from collections import Counter

import pytest
from helpers import make_config
from test_wm import SCREEN, info

from pywm import config
from pywm.core.keys import Key
from pywm.core.layouts import LAYOUTS
from pywm.core.rules import Rule
from pywm.core.wm import WindowManager


def test_there_are_between_one_and_nine_tags():
    assert 1 <= len(config.TAGS) <= 9


def test_initial_layout_exists():
    assert config.LAYOUT in LAYOUTS


def test_no_chord_is_bound_twice():
    dupes = [chord for chord, n in Counter(k.chord for k in config.KEYS).items() if n > 1]
    assert not dupes


def test_rules_are_rules():
    assert all(isinstance(r, Rule) for r in config.RULES)


def test_every_tag_gets_four_bindings():
    per_tag = Counter(
        k.args
        for k in config.KEYS
        if k.action.__name__ in {"view", "toggle_view", "tag", "toggle_tag"} and k.args != (0,)
    )
    assert set(per_tag.values()) == {4}
    assert len(per_tag) == len(config.TAGS)


@pytest.mark.parametrize("key", config.KEYS, ids=repr)
def test_every_binding_runs_with_its_arguments(key: Key):
    """Catches wrong argument counts and bad layout names, which Python cannot see until a call."""
    wm = WindowManager(make_config())
    wm.set_screens([SCREEN])
    wm.sync_app(1, [info(1), info(2), info(3)])
    wm.window_focused(1)
    key.action(wm, *key.args)
    wm.flush()
