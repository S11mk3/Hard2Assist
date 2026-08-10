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

# Only for known_folder() at the bottom of this file: shell32 knows where
# Documents actually is, and ole32 parses the id and frees the answer.
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)

WM_CLOSE = 0x0010
ERROR_ACCESS_DENIED = 5

# Restore puts a minimised window back at the size the user last gave it,
# rather than maximising it the way SW_SHOWMAXIMIZED would. It undoes either
# state, so it is the way back from both `fullscreen` and `minimize`.
SW_RESTORE = 9

# Minimise and let Windows activate whatever was behind, exactly as clicking
# the minimise button does. SW_SHOWMINNOACTIVE would leave the focus sitting
# on a window that is no longer on screen.
SW_MINIMIZE = 6

# Maximise and activate, exactly as clicking the maximise button does. This is
# as close to "fullscreen" as an outside program can get: true fullscreen is
# something each app implements for itself -- usually on F11 -- so there is no
# call that imposes it on an app that has none.
SW_SHOWMAXIMIZED = 3

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
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsZoomed.restype = wintypes.BOOL
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
    # WinError() builds the OSError itself, carrying the Windows error code and
    # its description; wrapping it in another OSError would bury both.
    raise ctypes.WinError(ctypes.get_last_error())


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


def minimize_window(hwnd):
    """Send a window to the taskbar. The opposite of focus_window().

    Returns True only if the window really ended up minimised. ShowWindow's
    own return value reports whether the window *was* visible beforehand, not
    whether the request was carried out, so the result is read back from
    IsIconic instead -- an elevated window ignores the request in silence
    (the same UIPI rule that blocks close), and the caller needs to be able
    to say so rather than claim a minimise that never happened.
    """
    if user32.IsIconic(hwnd):
        return True  # already out of the way

    user32.ShowWindow(hwnd, SW_MINIMIZE)

    return bool(user32.IsIconic(hwnd))


def maximize_window(hwnd):
    """Fill the screen with a window. The opposite of restore_window().

    As close to fullscreen as an outside program can get -- see
    SW_SHOWMAXIMIZED.

    Returns True only if the window really ended up maximised. Read back from
    IsZoomed for the same reason minimize_window() reads IsIconic: ShowWindow's
    own return value reports whether the window *was* visible beforehand, not
    whether the request was carried out, and an elevated window ignores it in
    silence.
    """
    if user32.IsZoomed(hwnd):
        return True  # already filling the screen

    user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)

    return bool(user32.IsZoomed(hwnd))


def restore_window(hwnd):
    """Put a window back to the size the user last gave it.

    SW_RESTORE undoes maximised and minimised alike, so this is the way back
    from `fullscreen` and from `minimize` both -- which is what lets `shrink`
    take "restore" as an alias without the word having to mean two things.

    Returns True only if the window really came back, read back from IsZoomed
    and IsIconic for the same reason maximize_window() does.
    """
    if not user32.IsZoomed(hwnd) and not user32.IsIconic(hwnd):
        return True  # already at its normal size

    user32.ShowWindow(hwnd, SW_RESTORE)

    return not user32.IsZoomed(hwnd) and not user32.IsIconic(hwnd)


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


# -- typing ------------------------------------------------------------------
#
# send_text() and send_keys() go through SendInput rather than the keybd_event
# above. keybd_event is enough for the volume keys, which are the same on every
# keyboard, but not for text: it sends a key *position*, so the letters that
# come out depend on the user's layout. SendInput can send a character instead
# (KEYEVENTF_UNICODE), which types the same thing on every layout in the world.

KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12          # Alt
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_BACK = 0x08
VK_DELETE = 0x2E
VK_HOME = 0x24
VK_END = 0x23
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        # ULONG_PTR: pointer-sized, so it must not be a plain DWORD on 64-bit.
        # wintypes.WPARAM is exactly that type under another name.
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _MOUSEINPUT(ctypes.Structure):
    """Declared only for its size.

    INPUT is a union, and Windows sizes it by its largest member -- which is
    the mouse one, not the keyboard one. Leaving this out makes sizeof(INPUT)
    too small, and SendInput then rejects every event and returns 0 without
    setting an error, which looks exactly like nothing happening at all.
    """
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _key_event(vk=0, scan=0, flags=0):
    event = _INPUT(type=INPUT_KEYBOARD)
    event.union.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags,
                                 time=0, dwExtraInfo=0)
    return event


def _send(events):
    """Inject a batch of input events. False if Windows refused them.

    Sent as one array rather than one call per event, so the user's own
    keystrokes cannot land in the middle of what is being typed.

    A refusal is normally UIPI: injected input cannot reach a window owned by
    an elevated process, the same rule that stops `close` from reaching Task
    Manager. There is nothing to be done about it here beyond reporting it, so
    the caller gets a False rather than an exception.
    """
    if not events:
        return True

    array = (_INPUT * len(events))(*events)
    sent = user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))

    return sent == len(events)


def send_text(text):
    """Type text into whatever window has focus. False if Windows refused.

    Iterated in UTF-16 code units rather than characters, because that is what
    a keyboard event carries. Anything outside the basic multilingual plane is
    two units, and sending both in order is what makes it arrive intact
    instead of as a pair of question marks.
    """
    if not text:
        return True

    units = text.encode("utf-16-le")

    events = []
    for i in range(0, len(units), 2):
        code = units[i] | (units[i + 1] << 8)
        events.append(_key_event(scan=code, flags=KEYEVENTF_UNICODE))
        events.append(_key_event(scan=code,
                                 flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))

    return _send(events)


def send_keys(*vks):
    """Press keys together and release them: send_keys(VK_CONTROL, 0x53).

    Pressed in the order given and released in reverse, which is how a person
    holds down control and then taps S. Releasing in the same order instead
    would let go of control first, and the chord would not register.
    """
    events = [_key_event(vk=vk) for vk in vks]
    events += [_key_event(vk=vk, flags=KEYEVENTF_KEYUP) for vk in reversed(vks)]

    return _send(events)


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


def foreground_title():
    """The title of the window in front, or "".

    What `type` names in its confirmation. Typed keys go wherever the focus
    is, so the title of that window is the only honest answer to "where did
    that text land".
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    return _title_of(hwnd)


# -- known folders -----------------------------------------------------------


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_GUID)]
ole32.CLSIDFromString.restype = ctypes.c_long
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
ole32.CoTaskMemFree.restype = None
shell32.SHGetKnownFolderPath.argtypes = [
    ctypes.POINTER(_GUID), wintypes.DWORD, wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_wchar_p),
]
shell32.SHGetKnownFolderPath.restype = ctypes.c_long


def known_folder(guid):
    """Where a Windows known folder really is, or "" if it has no path.

    Asked of Windows rather than assembled from the home directory, because
    Documents and Pictures are routinely redirected into OneDrive. Guessing
    "%USERPROFILE%\\Documents" then points at an empty leftover folder that is
    not the one the user means, and it looks like the app opened the wrong
    thing for no reason.

    `guid` is the known folder id as its usual braced string.
    """
    parsed = _GUID()
    if ole32.CLSIDFromString(guid, ctypes.byref(parsed)) != 0:
        return ""

    path = ctypes.c_wchar_p()
    if shell32.SHGetKnownFolderPath(ctypes.byref(parsed), 0, None,
                                    ctypes.byref(path)) != 0:
        return ""

    try:
        return path.value or ""
    finally:
        # Windows allocated the string and expects it back. Skipping this
        # leaks a little memory on every call.
        ole32.CoTaskMemFree(path)
