"""All Windows API (ctypes) code in one place.

Keeping the Win32 calls here lets the command modules stay plain Python.
An app's windows are found by enumerating every top-level window on demand
rather than remembering handles from launch time -- Windows recycles window
handles, so a stored one can end up pointing at an unrelated window.
"""

import ctypes
from ctypes import wintypes

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)

WM_CLOSE = 0x0010
ERROR_ACCESS_DENIED = 5

# Callback type for EnumWindows, which passes each top-level window handle
# to a function we supply.
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
)

# Declaring argtypes/restype matters on 64-bit Windows: HWND is pointer-sized,
# and without them ctypes passes it as a 32-bit int and truncates large handles.
user32.EnumWindows.argtypes = [ENUM_WINDOWS_PROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.PostMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


class AccessDenied(Exception):
    """Windows refused because the target runs at a higher privilege level.

    A normal process may not send messages to a window owned by an elevated
    one (Task Manager, Registry Editor, the .msc consoles) -- Windows calls
    this UIPI. The only workaround is running Hard2Assist as administrator.
    """


def _title_of(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_of(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def visible_windows():
    """Every visible, titled top-level window, as (hwnd, title, class_name)."""
    found = []

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = _title_of(hwnd)
            if title:
                found.append((hwnd, title, _class_of(hwnd)))
        return True  # continue enumerating

    user32.EnumWindows(ENUM_WINDOWS_PROC(callback), 0)
    return found


def windows_of(app):
    """Handles of the windows belonging to this App.

    Matches on window class when the app defines one (explorer's title is
    just the current folder name), otherwise on a title substring.

    Titles are only a guess for Start Menu apps -- the shortcut is named
    after the product while the window often is not -- so when title matching
    finds nothing, ownership is checked by process name instead. That costs
    a process lookup per window, which is why it is the fallback rather than
    the first attempt.
    """
    if not app.window_class and not app.title:
        return []

    windows = visible_windows()

    matches = []
    for hwnd, title, class_name in windows:
        if app.window_class and class_name != app.window_class:
            continue
        if app.title and app.title.lower() not in title.lower():
            continue
        matches.append(hwnd)

    if matches:
        return matches

    return [hwnd for hwnd, _title, class_name in windows
            if not (app.window_class and class_name != app.window_class)
            and app.owns_process(process_of_window(hwnd))]


def newest_window_of(app):
    """The most recently started window of this app, or None.

    "Most recently started" means the window whose owning process started
    last -- each console window, for example, is its own cmd.exe process.
    This is what makes `close cmd` shut the one just opened instead of every
    console on screen.

    Windows sharing one process (explorer's folder windows) have identical
    start times. EnumWindows returns windows in Z-order, front first, and
    max() keeps the first of equal values, so ties break towards the window
    nearest the front.
    """
    handles = windows_of(app)
    if not handles:
        return None

    def started_at(hwnd):
        try:
            return psutil.Process(pid_of_window(hwnd)).create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0  # unknown; treat as oldest

    return max(handles, key=started_at)


def close_window(hwnd):
    """Ask a window to close, equivalent to clicking its X button.

    The app can still prompt to save unsaved work. Raises AccessDenied when
    the window belongs to an elevated process.
    """
    ctypes.set_last_error(0)
    if user32.PostMessageW(hwnd, WM_CLOSE, 0, 0):
        return

    if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
        raise AccessDenied
    raise OSError(ctypes.WinError(ctypes.get_last_error()))


# Media and volume virtual-key codes. Windows treats these as keystrokes from
# a keyboard with media buttons and routes them to whatever is playing --
# Spotify, a YouTube tab, VLC -- with no need to know which.
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREVIOUS = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_KEYUP = 0x0002


def tap_key(vk, times=1):
    """Press and release a virtual key, as though typed on a real keyboard."""
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def pid_of_window(hwnd):
    """The id of the process that owns a window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_of_window(hwnd):
    """The image name owning a window ("opera.exe"), or "" if it cannot be read.

    Windows hides elevated processes from ordinary ones, so this returns ""
    for any window running as administrator.
    """
    try:
        return psutil.Process(pid_of_window(hwnd)).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return ""
