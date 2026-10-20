"""Test helpers. `make_config` is how a test says "the real config, except ..."."""

from types import SimpleNamespace

from pywm import config


def make_config(**overrides) -> SimpleNamespace:
    """A copy of pywm.config with some UPPERCASE settings replaced. No gaps and no bar by default,
    which keeps the arithmetic in tests readable."""
    settings = {k: v for k, v in vars(config).items() if k.isupper()}
    settings.update(GAP=0, BAR_ENABLED=False)
    settings.update(overrides)
    return SimpleNamespace(**settings)
