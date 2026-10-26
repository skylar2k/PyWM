"""Every Platform implementation must override every Platform method.

The implementations inherit from the `Platform` protocol (so editors can find them), and a class that
inherits a protocol method without overriding it gets the protocol's `...` body: a call that silently
does nothing. This test turns that mistake into a failure.
"""

from typing import get_protocol_members

import pytest
from fake_platform import FakePlatform

from pywm.platform import Platform


def missing(cls: type) -> list[str]:
    """Protocol members that `cls` takes from `Platform` itself instead of defining."""
    return sorted(
        name for name in get_protocol_members(Platform) if getattr(cls, name, None) is getattr(Platform, name)
    )


def test_fake_platform_overrides_every_method():
    assert missing(FakePlatform) == []


def test_macos_platform_overrides_every_method():
    pytest.importorskip("AppKit")
    from pywm.platform.macos.platform import MacOSPlatform

    assert missing(MacOSPlatform) == []


def test_the_check_notices_a_forgotten_method():
    class Forgetful(Platform):
        def screens(self):
            return []

    assert "spawn" in missing(Forgetful)
