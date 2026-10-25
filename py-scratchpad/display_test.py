from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApplicationDidChangeScreenParametersNotification,
)
from Foundation import NSNotificationCenter
from PyObjCTools import AppHelper
from Quartz import CGDisplayRegisterReconfigurationCallback


def on_cg(display, flags, info):
    print("CG callback", display, hex(flags), flush=True)


def on_ns(note):
    print("NSApplication notification", flush=True)


app = NSApplication.sharedApplication()
app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon

print("register ->", CGDisplayRegisterReconfigurationCallback(on_cg, None), flush=True)
observer = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
    NSApplicationDidChangeScreenParametersNotification, None, None, on_ns
)
AppHelper.runEventLoop()  # runs NSApplication properly; Ctrl-C works
