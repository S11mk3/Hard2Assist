"""The only Windows API code in the project.

Everything ctypes lives here so the command modules stay plain Python. We find
an app's windows by looking at every top-level window, rather than remembering
handles from when we launched it -- handles get recycled by Windows, and a stale
one can point at somebody else's window.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

WM_CLOSE = 0x0010
ERROR_ACCESS_DENIED = 5

# EnumWindows hands each window handle to a callback we supply.
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
)

# Declaring these matters on 64-bit Windows: a HWND is pointer-sized, and
# without argtypes ctypes would pass it as a 32-bit int and mangle big handles.
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

    A normal process is not allowed to send messages to a window owned by an
    elevated one (Task Manager, Registry Editor, the .msc consoles). Windows
    calls this UIPI. The only fix is to run Hard2Assist as administrator too.
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
    """Every visible top-level window that has a title, as (hwnd, title, class)."""
    found = []

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = _title_of(hwnd)
            if title:
                found.append((hwnd, title, _class_of(hwnd)))
        return True  # keep enumerating

    user32.EnumWindows(ENUM_WINDOWS_PROC(callback), 0)
    return found


def windows_of(app):
    """Handles of the windows belonging to this App.

    Matches on window class when the app defines one (explorer's title is just
    the folder you are looking at), otherwise on a title substring.
    """
    if not app.window_class and not app.title:
        return []

    matches = []
    for hwnd, title, class_name in visible_windows():
        if app.window_class and class_name != app.window_class:
            continue
        if app.title and app.title.lower() not in title.lower():
            continue
        matches.append(hwnd)
    return matches


def close_window(hwnd):
    """Ask a window to close, the same as clicking its X. The app can still
    prompt to save unsaved work.

    Raises AccessDenied if the window belongs to an elevated process.
    """
    ctypes.set_last_error(0)
    if user32.PostMessageW(hwnd, WM_CLOSE, 0, 0):
        return

    if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
        raise AccessDenied
    raise OSError(ctypes.WinError(ctypes.get_last_error()))


def pid_of_window(hwnd):
    """The process id that owns a window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value
