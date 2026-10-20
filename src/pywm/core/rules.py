"""Window rules: dwm's `rules[]` table, matched against app name, bundle id and title."""

import re
from dataclasses import dataclass

from pywm.core.types import WindowInfo


@dataclass(frozen=True, slots=True)
class Rule:
    """All given fields must match (regex search). The first matching rule wins."""

    app: str | None = None  # matched against the app name *or* the bundle id
    title: str | None = None
    floating: bool | None = None
    tag: int | None = None  # 1-based tag number
    monitor: int | None = None  # index into the left-to-right monitor list
    ignore: bool = False  # never manage this window at all

    def matches(self, info: WindowInfo) -> bool:
        if self.app and not (re.search(self.app, info.app) or re.search(self.app, info.bundle_id)):
            return False
        return not (self.title and not re.search(self.title, info.title))


def first_match(rules: tuple[Rule, ...], info: WindowInfo) -> Rule | None:
    return next((r for r in rules if r.matches(info)), None)
