"""Builds pywm.app with py2app.   cd packaging && uv run python setup.py py2app -A

Kept in its own folder, away from the root pyproject.toml: py2app refuses projects that declare
`install_requires`, which setuptools would otherwise read from [project].dependencies.

-A is "alias mode": the app is a real bundle (own Dock-less identity, own permissions) whose
launcher points back at this source tree and the project's virtualenv. So editing
src/pywm/config.py and relaunching is enough; nothing needs rebuilding.
"""

from setuptools import setup

setup(
    app=["pywm_app.py"],
    options={
        "py2app": {
            "packages": ["pywm"],
            "plist": {
                "CFBundleName": "pywm",
                "CFBundleIdentifier": "dev.pywm.pywm",
                "LSUIElement": True,  # no Dock icon and no entry in the app switcher
            },
        }
    },
)
