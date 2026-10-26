"""The command line: this part is already written, so these should pass from the start."""

import io
import sys

import pytest

from pymenu import cli, config


def test_defaults_come_from_config_py():
    s = cli.parse([])
    assert (s.topbar, s.lines, s.prompt, s.font) == (config.TOPBAR, config.LINES, config.PROMPT, config.FONT)
    assert s.colors == config.COLORS and not s.ignore_case


def test_flags_override_the_defaults():
    s = cli.parse(
        [
            "-b",
            "-i",
            "-l",
            "5",
            "-m",
            "1",
            "-p",
            "run:",
            "-fn",
            "Menlo:size=20",
            "-nb",
            "#000000",
            "-sf",
            "ffffff",
        ]
    )
    assert (s.topbar, s.ignore_case, s.lines, s.monitor, s.prompt, s.font) == (
        False,
        True,
        5,
        1,
        "run:",
        "Menlo:size=20",
    )
    assert (s.colors["norm_bg"], s.colors["sel_fg"]) == (0x000000, 0xFFFFFF)
    assert s.colors["norm_fg"] == config.COLORS["norm_fg"]  # untouched


def test_bundled_short_flags_and_multi_letter_options_do_not_clash():
    s = cli.parse(["-bi", "-fn", "Menlo"])  # -b -i, then -fn (not -f then n)
    assert (s.topbar, s.ignore_case, s.font, s.fast) == (False, True, "Menlo", False)


def test_a_negative_line_count_means_a_horizontal_list():
    assert cli.parse(["-l", "-3"]).lines == 0


@pytest.mark.parametrize("bad", ["red", "#12345", "#gggggg"])
def test_a_bad_colour_is_a_usage_error(bad):
    with pytest.raises(SystemExit):
        cli.parse(["-nb", bad])


def test_version_flag_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as e:
        cli.parse(["-v"])
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("pymenu-")


@pytest.mark.parametrize(
    ("data", "expected"),
    [("a\nb\n", ["a", "b"]), ("a\nb", ["a", "b"]), ("", []), ("a\n\nb\n", ["a", "", "b"]), ("\n", [""])],
)
def test_items_are_the_lines_of_stdin(data, expected):
    assert cli.read_items(io.StringIO(data)) == expected


def test_emit_prints_one_line_immediately(capsys):
    cli.emit("chosen")
    assert capsys.readouterr().out == "chosen\n"


def test_main_hands_items_and_settings_to_the_app_and_returns_its_exit_status(monkeypatch):
    seen = {}

    def fake_run(items, settings, emit):
        seen.update(items=items, settings=settings, emit=emit)
        return 3

    monkeypatch.setattr(sys, "stdin", io.StringIO("x\ny\n"))
    monkeypatch.setattr("pymenu.app.run", fake_run)
    assert cli.main(["-p", "pick:"]) == 3
    assert seen["items"] == ["x", "y"] and seen["settings"].prompt == "pick:" and seen["emit"] is cli.emit


def test_centering_is_off_by_default_with_a_700_point_width():
    s = cli.parse([])
    assert (s.center, s.width, s.lines) == (False, 700, 0)


def test_dash_c_centres_and_defaults_to_a_ten_line_list():
    s = cli.parse(["-c"])
    assert (s.center, s.lines) == (True, config.CENTER_LINES)


def test_dash_l_wins_over_the_centred_default():
    assert cli.parse(["-c", "-l", "4"]).lines == 4
    assert cli.parse(["-c", "-l", "0"]).lines == 0  # an explicit -l 0 asks for a horizontal row: honoured


def test_dash_capital_w_sets_the_width():
    assert cli.parse(["-c", "-W", "500"]).width == 500
    assert cli.parse(["-W", "0"]).width == 1  # never zero
