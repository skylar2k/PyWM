"""STEP 1 spec: pymenu.match.match(). Make these pass first."""

from pymenu.match import match


def test_empty_text_matches_everything_in_the_original_order():
    assert match(["b", "a", "c"], "") == ["b", "a", "c"]


def test_only_spaces_count_as_no_text_at_all():
    assert match(["a", "b"], "   ") == ["a", "b"]


def test_nothing_matching_gives_an_empty_list():
    assert match(["alpha", "beta"], "zzz") == []


def test_exact_match_first_then_prefix_then_substring():
    items = ["xfire", "firefox", "fire", "campfire"]
    assert match(items, "fire") == ["fire", "firefox", "xfire", "campfire"]


def test_each_group_keeps_the_original_relative_order():
    assert match(["fb", "fa", "af", "ab"], "f") == ["fb", "fa", "af"]


def test_every_space_separated_token_must_appear_somewhere_in_the_item():
    items = ["open the file", "file open", "opener", "close file"]
    assert match(items, "file open") == ["file open", "open the file"]


def test_prefix_is_judged_by_the_first_token_only():
    assert match(["b a", "a b", "xa b"], "a b") == ["a b", "b a", "xa b"]


def test_extra_spaces_between_and_around_tokens_make_no_empty_tokens():
    assert match(["a b", "b a"], "  a   b ") == ["a b", "b a"]


def test_matching_is_case_sensitive_by_default():
    assert match(["Firefox", "firefox"], "fire") == ["firefox"]


def test_ignore_case_applies_to_substring_prefix_and_exact():
    assert match(["Firefox", "firefox"], "FIRE", ignore_case=True) == ["Firefox", "firefox"]
    assert match(["xFire", "FIRE", "fire"], "fire", ignore_case=True) == ["FIRE", "fire", "xFire"]
