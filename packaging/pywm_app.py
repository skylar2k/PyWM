"""The entry script py2app wraps into pywm.app. The bundler only ever needs to know about this file."""

from pywm.app import main

raise SystemExit(main())
