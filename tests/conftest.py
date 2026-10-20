import pytest
from fake_platform import FakePlatform
from helpers import make_config

from pywm.controller import Controller
from pywm.core.wm import WindowManager


@pytest.fixture
def config():
    return make_config()


@pytest.fixture
def platform() -> FakePlatform:
    return FakePlatform()


@pytest.fixture
def ctl(platform: FakePlatform, config) -> Controller:
    return Controller(platform, WindowManager(config), config.KEYS)
