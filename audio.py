"""Reading and setting the exact system volume.

The media keys can only nudge the volume up and down a notch at a time, which
is no use for "set it to fifty". That needs the Windows audio API, which pycaw
wraps.

COM objects belong to the thread that made them, and commands run on the
microphone thread, so the endpoint is kept per thread.
"""

import threading

_local = threading.local()


def _endpoint():
    """The speakers' volume control, or None if this PC will not give us one."""
    if getattr(_local, "tried", False):
        return _local.endpoint

    _local.tried = True
    _local.endpoint = None

    try:
        # Same rule as the voice: COM has to be switched on for this thread
        # before anything will hand us an interface.
        import comtypes
        comtypes.CoInitialize()

        from pycaw.utils import AudioUtilities
        _local.endpoint = AudioUtilities.GetSpeakers().EndpointVolume
    except Exception:
        _local.endpoint = None

    return _local.endpoint


def available():
    return _endpoint() is not None


def level():
    """Current volume, 0 to 100, or None."""
    endpoint = _endpoint()
    if endpoint is None:
        return None
    try:
        return round(endpoint.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        return None


def set_level(percent):
    """Set the volume. Returns the level it ended up at, or None on failure."""
    endpoint = _endpoint()
    if endpoint is None:
        return None

    percent = max(0, min(100, int(percent)))
    try:
        # Setting a level while muted looks broken -- you turn it up and hear
        # nothing -- so unmute at the same time.
        if percent > 0 and endpoint.GetMute():
            endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(percent / 100, None)
    except Exception:
        return None

    return percent
