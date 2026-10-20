import pytest

from pywm.core.keys import Key, Mod


def test_modifiers_combine_like_flags():
    assert Mod(5) == Mod.ALT | Mod.SHIFT
    assert Mod.SHIFT in (Mod.ALT | Mod.SHIFT)


def test_key_holds_its_function_and_arguments_and_exposes_a_chord():
    def action(wm, a, b):
        pass

    k = Key(Mod.ALT | Mod.SHIFT, "j", action, 1, "x")
    assert k.chord == (Mod.ALT | Mod.SHIFT, "j")
    assert k.action is action and k.args == (1, "x")


def test_unknown_key_name_fails_immediately():
    with pytest.raises(ValueError, match="unknown key"):
        Key(Mod.ALT, "nonsense", print)
