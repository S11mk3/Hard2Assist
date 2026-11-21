"""Reading and setting the exact system volume through the Windows Core Audio API (pycaw).

The volume keys only move a notch at a time, so "volume fifty" needs this instead.
"""

import threading

# The endpoint is a COM object, which belongs to the thread that made it, so one per thread.
_local = threading.local()


def _endpoint():
    """The speakers' volume control, or None if this PC has none we can reach."""
    if not hasattr(_local, "endpoint"):
        _local.endpoint = None
        try:
            import comtypes
            comtypes.CoInitialize()

            from pycaw.utils import AudioUtilities
            _local.endpoint = AudioUtilities.GetSpeakers().EndpointVolume
        except Exception:
            pass
    return _local.endpoint


def _ask(action):
    """action(endpoint)'s result, or None if the endpoint is missing or refuses."""
    endpoint = _endpoint()
    if endpoint is None:
        return None
    try:
        return action(endpoint)
    except Exception:
        return None


def is_muted():
    """True or False, or None if unreadable."""
    return _ask(lambda endpoint: bool(endpoint.GetMute()))


def get_level():
    """The volume as a percentage, or None if unreadable."""
    return _ask(lambda endpoint: round(endpoint.GetMasterVolumeLevelScalar() * 100))


def set_level(percent):
    """Set the volume, unmuting if needed. Returns the level set, or None on failure."""
    percent = max(0, min(100, int(percent)))

    def apply(endpoint):
        # A level set while muted changes nothing anyone can hear.
        if percent > 0 and endpoint.GetMute():
            endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(percent / 100, None)
        return percent

    return _ask(apply)
