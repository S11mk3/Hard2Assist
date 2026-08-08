"""Reading and setting the exact system volume.

The media keys can only nudge the volume one notch at a time, which is no use
for "set it to fifty" -- that requires the Windows Core Audio API, accessed
through pycaw.

COM objects are bound to the thread that created them, and commands run on
the microphone thread, so the audio endpoint is cached per thread.
"""

import threading

_local = threading.local()


def _endpoint():
    """The speakers' volume-control interface, or None if unavailable."""
    if getattr(_local, "tried", False):
        return _local.endpoint

    _local.tried = True
    _local.endpoint = None

    try:
        # COM must be initialised on this thread before any interface can
        # be obtained (same requirement as the speech voice).
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
    """Current volume as 0-100, or None if it cannot be read."""
    endpoint = _endpoint()
    if endpoint is None:
        return None
    try:
        return round(endpoint.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        return None


def set_level(percent):
    """Set the volume. Returns the resulting level, or None on failure."""
    endpoint = _endpoint()
    if endpoint is None:
        return None

    percent = max(0, min(100, int(percent)))
    try:
        # Setting a level while muted appears broken (the volume goes up but
        # nothing is heard), so unmute at the same time.
        if percent > 0 and endpoint.GetMute():
            endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(percent / 100, None)
    except Exception:
        return None

    return percent
