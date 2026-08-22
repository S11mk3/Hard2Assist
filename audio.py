"""Setting an exact system volume through the Windows Core Audio API.

The media keys can only nudge the volume a notch at a time, so "set it to
fifty" needs this instead. Reached through pycaw.
"""

import threading

# The endpoint is a COM object, and a COM object belongs to the thread that
# created it. Commands run on the microphone thread, so it is cached per thread.
_local = threading.local()


def _endpoint():
    """The speakers' volume-control interface, or None if unavailable."""
    if getattr(_local, "tried", False):
        return _local.endpoint

    _local.tried = True
    _local.endpoint = None

    try:
        # COM must be initialised on a thread before it can obtain an
        # interface, the same requirement the speech voice has.
        import comtypes
        comtypes.CoInitialize()

        from pycaw.utils import AudioUtilities
        _local.endpoint = AudioUtilities.GetSpeakers().EndpointVolume
    except Exception:
        _local.endpoint = None

    return _local.endpoint



def is_muted():
    """Whether the speakers are muted right now, or None if unreadable."""
    endpoint = _endpoint()
    if endpoint is None:
        return None

    try:
        return bool(endpoint.GetMute())
    except Exception:
        return None


def set_level(percent):
    """Set the volume. Returns the resulting level, or None on failure."""
    endpoint = _endpoint()
    if endpoint is None:
        return None

    percent = max(0, min(100, int(percent)))
    try:
        # A level set while muted takes effect silently, so unmute with it.
        if percent > 0 and endpoint.GetMute():
            endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(percent / 100, None)
    except Exception:
        return None

    return percent
