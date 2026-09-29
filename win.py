"""All Windows API (ctypes) code, in one place.

Keeping the Win32 calls here lets the command modules stay plain Python.
An app's windows are found by enumerating every top-level window on demand
rather than remembering handles: Windows recycles window handles, so a stored
one can end up pointing at an unrelated window.
"""

import ctypes
import os
import re
from ctypes import wintypes

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# For known_folder() at the bottom of this file: shell32 knows where Documents
# actually is, and ole32 parses the id and frees the answer.
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)

WM_CLOSE = 0x0010
ERROR_ACCESS_DENIED = 5

# Puts a minimised or maximised window back at the size the user last gave it.
# It undoes either state, so it is the way back from both `fullscreen` and
# `minimize`.
SW_RESTORE = 9

# Minimise and let Windows activate whatever was behind, as clicking the
# minimise button does. SW_SHOWMINNOACTIVE would leave the focus on a window
# that is no longer on screen.
SW_MINIMIZE = 6

# Maximise and activate, as clicking the maximise button does. This is as
# close to "fullscreen" as an outside program can get: true fullscreen is
# something each app implements for itself, usually on F11.
SW_SHOWMAXIMIZED = 3

# Callback type for EnumWindows, which passes each top-level window handle to
# a function we supply.
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
)

# argtypes/restype matter on 64-bit Windows: HWND is pointer-sized, and
# without them ctypes passes it as a 32-bit int and truncates large handles.
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
    one (Task Manager, Registry Editor, the .msc consoles); Windows calls this
    UIPI. The only workaround is running Hard2Assist as administrator.
    """


def _title_of(hwnd):
    """A window's title text."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_of(hwnd):
    """A window's Win32 class name."""
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

    Matches on window class when the app defines one (explorer's title is just
    the current folder name), otherwise on a title substring.

    Titles are only a guess for Start Menu apps, where the shortcut is named
    after the product and the window often is not, so a title match that finds
    nothing falls back to checking ownership by process name. That costs a
    process lookup per window, which is why it is the fallback.
    """
    if app.kind == "itself":
        # Our own windows, found by process id rather than title: a browser
        # tab or a folder named "Hard2Assist" must not be mistaken for us.
        ours = os.getpid()
        return [hwnd for hwnd, _title, _class_name in visible_windows()
                if pid_of_window(hwnd) == ours]

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
    last -- each console window, for example, is its own cmd.exe. This is what
    makes `close cmd` shut the one just opened rather than every console.

    Windows sharing one process (explorer's folder windows) have identical
    start times. EnumWindows returns them in Z-order, front first, and max()
    keeps the first of equal values, so ties break towards the front.
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
    """Ask a window to close, as clicking its X button does.

    The app can still prompt to save unsaved work. Raises AccessDenied when
    the window belongs to an elevated process.
    """
    ctypes.set_last_error(0)
    if user32.PostMessageW(hwnd, WM_CLOSE, 0, 0):
        return

    if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
        raise AccessDenied
    # WinError() builds the OSError itself, carrying the Windows error code
    # and its description.
    raise ctypes.WinError(ctypes.get_last_error())


def focus_window(hwnd):
    """Bring a window to the front, restoring it if it was minimised.

    Windows only lets the process that already owns the foreground hand it
    away, so a background app calling SetForegroundWindow usually just flashes
    the taskbar button. Attaching to the foreground window's input queue first
    makes Windows treat the request as coming from that thread.

    Returns True only if the window really ended up in front, so the caller
    can report a refusal rather than claim a switch that did not happen.
    """
    foreground = user32.GetForegroundWindow()
    if foreground == hwnd and not user32.IsIconic(hwnd):
        return True

    ours = kernel32.GetCurrentThreadId()
    theirs = user32.GetWindowThreadProcessId(foreground, None)

    # Nothing to attach to when there is no foreground window, or when it is
    # already ours: AttachThreadInput fails if both ids are the same.
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

    Returns True only if the window really ended up minimised, read back from
    IsIconic: ShowWindow's own return value reports whether the window *was*
    visible beforehand, not whether the request was carried out, and an
    elevated window ignores the request in silence.
    """
    if user32.IsIconic(hwnd):
        return True  # already out of the way

    user32.ShowWindow(hwnd, SW_MINIMIZE)

    return bool(user32.IsIconic(hwnd))


def maximize_window(hwnd):
    """Fill the screen with a window. The opposite of restore_window().

    As close to fullscreen as an outside program can get; see
    SW_SHOWMAXIMIZED.

    Returns True only if the window really ended up maximised, read back from
    IsZoomed for the reason given in minimize_window().
    """
    if user32.IsZoomed(hwnd):
        return True  # already filling the screen

    user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)

    return bool(user32.IsZoomed(hwnd))


def restore_window(hwnd):
    """Put a window back to the size the user last gave it.

    SW_RESTORE undoes maximised and minimised alike, so this is the way back
    from `fullscreen` and from `minimize` both.

    Returns True only if the window really came back, read back from IsZoomed
    and IsIconic for the reason given in minimize_window().
    """
    if not user32.IsZoomed(hwnd) and not user32.IsIconic(hwnd):
        return True  # already at its normal size

    user32.ShowWindow(hwnd, SW_RESTORE)

    return not user32.IsZoomed(hwnd) and not user32.IsIconic(hwnd)


# Volume virtual-key codes. Windows treats these as keystrokes from a keyboard
# with volume buttons, so they adjust the system volume like real presses.
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

# For `screenshot`: Win+PrintScreen is the chord Windows itself saves a PNG
# to Pictures\Screenshots for, so sending it needs no capture code at all.
VK_LWIN = 0x5B
VK_SNAPSHOT = 0x2C


# -- keys and typing ---------------------------------------------------------
#
# Every keystroke goes through SendInput. Besides virtual keys it can send a
# character (KEYEVENTF_UNICODE), which types the same thing whatever the
# user's keyboard layout, where a virtual key only names a key and the letter
# that comes out depends on the layout.

KEYEVENTF_KEYUP = 0x0002
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
        # ULONG_PTR: pointer-sized, so not a plain DWORD on 64-bit.
        # wintypes.WPARAM is that type under another name.
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class _MOUSEINPUT(ctypes.Structure):
    """Declared only for its size.

    INPUT is a union, and Windows sizes it by its largest member, which is the
    mouse one. Without this, sizeof(INPUT) is too small and SendInput rejects
    every event, returning 0 without setting an error.
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
    """One INPUT record describing a key press or release."""
    event = _INPUT(type=INPUT_KEYBOARD)
    event.union.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags,
                                 time=0, dwExtraInfo=0)
    return event


def _send(events):
    """Inject a batch of input events. False if Windows refused them.

    Sent as one array rather than one call per event, so the user's own
    keystrokes cannot land in the middle of what is being typed.

    A refusal is normally UIPI: injected input cannot reach a window owned by
    an elevated process, the same rule that stops `close` reaching Task
    Manager. Nothing can be done about it here, so the caller gets a False
    rather than an exception.
    """
    if not events:
        return True

    array = (_INPUT * len(events))(*events)
    sent = user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))

    return sent == len(events)


def send_text(text):
    """Type text into whatever window has focus. False if Windows refused.

    Iterated in UTF-16 code units rather than characters, because that is what
    a keyboard event carries: anything outside the basic multilingual plane is
    two units, and both must be sent in order for it to arrive intact.
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
    holds control and taps S. Releasing in the same order would let go of
    control first, and the chord would not register.
    """
    events = [_key_event(vk=vk) for vk in vks]
    events += [_key_event(vk=vk, flags=KEYEVENTF_KEYUP) for vk in reversed(vks)]

    return _send(events)


def tap_key(vk, times=1):
    """Press and release one key `times` times. False if Windows refused."""
    events = []
    for _ in range(times):
        events += [_key_event(vk=vk), _key_event(vk=vk, flags=KEYEVENTF_KEYUP)]

    return _send(events)


def pid_of_window(hwnd):
    """The id of the process that owns a window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_of_window(hwnd):
    """The image name owning a window ("opera.exe"), or "" if unreadable.

    Windows hides elevated processes from ordinary ones, so this returns ""
    for any window running as administrator.
    """
    try:
        return psutil.Process(pid_of_window(hwnd)).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return ""


def friendly_username():
    """The Windows account name when it reads like a real name, else "".

    Accounts are also called things like "marko-kg102", and being addressed
    by a login string is worse than not being addressed by name. Shared by
    the launch greeting and `stop`'s goodbye, so the two always agree.
    """
    name = os.environ.get("USERNAME", "").strip()
    if re.fullmatch(r"[A-Za-z]{2,20}", name):
        return name
    return ""


# -- clipboard ---------------------------------------------------------------

CF_UNICODETEXT = 13

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL


def clipboard_text():
    """The text on the clipboard, or "".

    What `remember website` reads: a URL cannot sensibly be dictated, but it
    can be copied from the browser's address bar first.
    """
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""

        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def foreground_is_ours():
    """Whether the window in front belongs to this process.

    Backs the "only listen while I'm in focus" setting. Comparing process ids
    rather than a remembered handle covers every window the app owns -- the
    main window, the file picker, a message box -- without tracking any.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    return pid_of_window(hwnd) == os.getpid()


def foreground_title():
    """The title of the window in front, or "".

    What `type` names in its confirmation: typed keys go wherever the focus
    is, so that window's title is the only honest answer to where they landed.
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
    Documents and Pictures are routinely redirected into OneDrive; guessing
    "%USERPROFILE%\\Documents" then points at an empty leftover folder.

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
        # Windows allocated the string and expects it back.
        ole32.CoTaskMemFree(path)
