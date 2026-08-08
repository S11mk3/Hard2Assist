"""All Windows API (ctypes) code in one place.

Keeping the Win32 calls here lets the command modules stay plain Python.
An app's windows are found by enumerating every top-level window on demand
rather than remembering handles from launch time -- Windows recycles window
handles, so a stored one can end up pointing at an unrelated window.
"""

import ctypes
import os
from ctypes import wintypes

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_CLOSE = 0x0010
ERROR_ACCESS_DENIED = 5

# Restore puts a minimised window back at the size the user last gave it,
# rather than maximising it the way SW_SHOWMAXIMIZED would.
SW_RESTORE = 9

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
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.AttachThreadInput.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.BOOL
]
user32.AttachThreadInput.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


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


def focus_window(hwnd):
    """Bring a window to the front, restoring it if it was minimised.

    Windows only lets the process that already owns the foreground hand it
    away, so a background app calling SetForegroundWindow by itself usually
    just flashes the taskbar button instead. Attaching to the foreground
    window's input queue first makes Windows treat the request as coming
    from that thread, which is the long-standing way around this.

    Returns True only if the window really ended up in front, so the caller
    can report a refusal rather than claim a switch that did not happen.
    """
    foreground = user32.GetForegroundWindow()
    if foreground == hwnd and not user32.IsIconic(hwnd):
        return True

    ours = kernel32.GetCurrentThreadId()
    theirs = user32.GetWindowThreadProcessId(foreground, None)

    # Nothing to attach to when there is no foreground window, or when it is
    # already ours. AttachThreadInput fails if both ids are the same.
    attached = (theirs and theirs != ours
                and user32.AttachThreadInput(ours, theirs, True))

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(ours, theirs, False)

    return user32.GetForegroundWindow() == hwnd


# Volume virtual-key codes. Windows treats these as keystrokes from a keyboard
# with volume buttons, so they adjust the system volume like real key presses.
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

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


def foreground_is_ours():
    """Whether the window in front belongs to this process.

    Backs the "only listen while I'm in focus" setting. Comparing process ids
    rather than a remembered handle covers every window the app owns -- the
    main window, the file picker, a message box -- without tracking any of them.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    return pid_of_window(hwnd) == os.getpid()
