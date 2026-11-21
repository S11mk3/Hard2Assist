"""Every Windows API call Hard2Assist makes, so the rest of the code stays plain Python.

An app's windows are found by enumerating on demand rather than by remembered handles: Windows
recycles handles, so a stored one can end up pointing at an unrelated window.
"""

import ctypes
import os
import re
import threading
from ctypes import wintypes as w

import psutil

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", w.WPARAM)]   # ULONG_PTR: pointer-sized, which WPARAM is


class _MOUSEINPUT(ctypes.Structure):
    """Declared only for its size: INPUT is a union sized by this, its largest member, and
    SendInput silently rejects every event when sizeof(INPUT) is wrong."""
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", w.WPARAM)]


class _INPUT(ctypes.Structure):
    class _UNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]
    _fields_ = [("type", w.DWORD), ("union", _UNION)]


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD), ("Data4", ctypes.c_ubyte * 8)]


ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)


def _api(dll, name, restype, *argtypes):
    """Declare a function's types. Without them ctypes passes 64-bit handles as 32-bit ints."""
    function = getattr(dll, name)
    function.restype, function.argtypes = restype, argtypes


_api(user32, "EnumWindows", w.BOOL, ENUM_WINDOWS_PROC, w.LPARAM)
_api(user32, "IsWindowVisible", w.BOOL, w.HWND)
_api(user32, "IsIconic", w.BOOL, w.HWND)
_api(user32, "IsZoomed", w.BOOL, w.HWND)
_api(user32, "GetWindowTextLengthW", ctypes.c_int, w.HWND)
_api(user32, "GetWindowTextW", ctypes.c_int, w.HWND, w.LPWSTR, ctypes.c_int)
_api(user32, "GetClassNameW", ctypes.c_int, w.HWND, w.LPWSTR, ctypes.c_int)
_api(user32, "GetWindowThreadProcessId", w.DWORD, w.HWND, ctypes.POINTER(w.DWORD))
_api(user32, "GetForegroundWindow", w.HWND)
_api(user32, "PostMessageW", w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_api(user32, "ShowWindow", w.BOOL, w.HWND, ctypes.c_int)
_api(user32, "BringWindowToTop", w.BOOL, w.HWND)
_api(user32, "SetForegroundWindow", w.BOOL, w.HWND)
_api(user32, "AttachThreadInput", w.BOOL, w.DWORD, w.DWORD, w.BOOL)
_api(user32, "SendInput", w.UINT, w.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_api(user32, "OpenClipboard", w.BOOL, w.HWND)
_api(user32, "CloseClipboard", w.BOOL)
_api(user32, "GetClipboardData", w.HANDLE, w.UINT)
_api(user32, "RegisterHotKey", w.BOOL, w.HWND, ctypes.c_int, w.UINT, w.UINT)
_api(user32, "GetMessageW", w.BOOL, ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
_api(kernel32, "GetCurrentThreadId", w.DWORD)
_api(kernel32, "GlobalLock", w.LPVOID, w.HGLOBAL)
_api(kernel32, "GlobalUnlock", w.BOOL, w.HGLOBAL)
_api(shell32, "IsUserAnAdmin", w.BOOL)
_api(shell32, "SHGetKnownFolderPath", ctypes.c_long, ctypes.POINTER(_GUID), w.DWORD, w.HANDLE,
     ctypes.POINTER(ctypes.c_wchar_p))
_api(ole32, "CLSIDFromString", ctypes.c_long, w.LPCWSTR, ctypes.POINTER(_GUID))
_api(ole32, "CoTaskMemFree", None, ctypes.c_void_p)
_api(dwmapi, "DwmGetWindowAttribute", ctypes.c_long, w.HWND, w.DWORD, ctypes.c_void_p, w.DWORD)

WM_CLOSE = 0x0010
WM_HOTKEY = 0x0312
ERROR_ACCESS_DENIED = 5
CF_UNICODETEXT = 13
DWMWA_CLOAKED = 14
SW_MAXIMIZE = 3
SW_MINIMIZE = 6    # activates whatever was behind, as the minimise button does
SW_RESTORE = 9     # undoes minimised and maximised alike
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOD_NOREPEAT = 0x4000

VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_LWIN = 0x5B
VK_SNAPSHOT = 0x2C
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF

# Spoken modifier names: (virtual key, RegisterHotKey flag).
MODIFIERS = {
    "control": (VK_CONTROL, 0x2), "ctrl": (VK_CONTROL, 0x2),
    "shift": (0x10, 0x4),
    "alt": (0x12, 0x1),
    "windows": (VK_LWIN, 0x8), "win": (VK_LWIN, 0x8),
}

# Spoken key names. Letters and digits are their own names.
KEYS = {
    "enter": VK_RETURN, "return": VK_RETURN, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "spacebar": 0x20, "backspace": 0x08, "back space": 0x08,
    "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23, "page up": 0x21, "page down": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}


class AccessDenied(Exception):
    """Windows refused because the target runs as administrator and Hard2Assist does not.

    Windows (UIPI) stops an ordinary program sending messages or keystrokes to an elevated
    one -- Task Manager, Registry Editor, the .msc consoles. Running Hard2Assist as
    administrator is the only way round it.
    """


# -- windows -------------------------------------------------------------------


def _title_of(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_of(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _cloaked(hwnd):
    """Whether Windows is hiding a "visible" window: a suspended Store app, another desktop."""
    value = w.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value))
    return bool(value.value)


def visible_windows():
    """Every titled top-level window the user can actually see, as (hwnd, title, class_name)."""
    found = []

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd) and not _cloaked(hwnd):
            title = _title_of(hwnd)
            if title:
                found.append((hwnd, title, _class_of(hwnd)))
        return True

    user32.EnumWindows(ENUM_WINDOWS_PROC(callback), 0)
    return found


def windows_of(app):
    """This App's windows, front first.

    Matched by window class where the app has one (Explorer titles a window after its folder),
    else by title. Titles are a guess for Start Menu apps, so when none matches, the windows
    whose process is the app's executable are used instead.
    """
    if app.kind == "itself":
        # By process id: a browser tab or folder named "Hard2Assist" is not us.
        return [hwnd for hwnd, _, _ in visible_windows() if pid_of_window(hwnd) == os.getpid()]

    if not app.window_class and not app.title:
        return []

    windows = [(hwnd, title) for hwnd, title, class_name in visible_windows()
               if not app.window_class or class_name == app.window_class]
    by_title = [hwnd for hwnd, title in windows if not app.title or app.title.lower() in title.lower()]
    return by_title or [hwnd for hwnd, _ in windows if app.owns_process(process_of_window(hwnd))]


def newest_window_of(app):
    """The app's window whose process started last, or None.

    This is what makes `close cmd` shut the console just opened by voice. Windows sharing one
    process (Explorer's) tie, and max() keeps the first, which is the frontmost.
    """
    def started_at(hwnd):
        try:
            return psutil.Process(pid_of_window(hwnd)).create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    return max(windows_of(app), key=started_at, default=None)


def close_window(hwnd):
    """Ask a window to close, as its X button does, so it can offer to save.

    Raises AccessDenied for an elevated window, OSError for anything else.
    """
    ctypes.set_last_error(0)
    if user32.PostMessageW(hwnd, WM_CLOSE, 0, 0):
        return
    if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
        raise AccessDenied
    raise ctypes.WinError(ctypes.get_last_error())


def focus_window(hwnd):
    """Bring a window to the front, restoring it if minimised. True only if it really got there.

    Windows only lets the foreground's owner give the foreground away, so a background app's
    SetForegroundWindow usually just flashes the taskbar. Attaching to the foreground window's
    input queue first makes the request count as coming from it.
    """
    foreground = user32.GetForegroundWindow()
    if foreground == hwnd and not user32.IsIconic(hwnd):
        return True

    ours = kernel32.GetCurrentThreadId()
    theirs = user32.GetWindowThreadProcessId(foreground, None)
    attached = theirs and theirs != ours and user32.AttachThreadInput(ours, theirs, True)
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(ours, theirs, False)

    return user32.GetForegroundWindow() == hwnd


# ShowWindow's return value says whether the window *was* visible, and an elevated window ignores
# the request in silence, so each of these reads the result back instead.

def minimize_window(hwnd):
    if not user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_MINIMIZE)
    return bool(user32.IsIconic(hwnd))


def maximize_window(hwnd):
    """As close to fullscreen as another program can get: true fullscreen is up to each app."""
    if not user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
    return bool(user32.IsZoomed(hwnd))


def restore_window(hwnd):
    """Back to the size the user gave it, from maximised or minimised."""
    if user32.IsZoomed(hwnd) or user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    return not user32.IsZoomed(hwnd) and not user32.IsIconic(hwnd)


def pid_of_window(hwnd):
    pid = w.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_of_window(hwnd):
    """The executable owning a window ("opera.exe"), or "" -- always "" for an elevated one."""
    try:
        return psutil.Process(pid_of_window(hwnd)).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return ""


def foreground():
    """The window in front, or None."""
    return user32.GetForegroundWindow()


def foreground_is_ours():
    """Whether the window in front belongs to this process: main window, file picker or dialog."""
    hwnd = user32.GetForegroundWindow()
    return bool(hwnd) and pid_of_window(hwnd) == os.getpid()


def foreground_title():
    hwnd = user32.GetForegroundWindow()
    return _title_of(hwnd) if hwnd else ""


# -- keys and typing -------------------------------------------------------------
#
# Everything goes through SendInput in one batch, so the user's own keystrokes cannot land in the
# middle. A refusal is nearly always UIPI (see AccessDenied), reported as False.

def _key_event(vk=0, scan=0, flags=0):
    event = _INPUT(type=INPUT_KEYBOARD)
    event.union.ki = _KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return event


def _send(events):
    if not events:
        return True
    array = (_INPUT * len(events))(*events)
    return user32.SendInput(len(events), array, ctypes.sizeof(_INPUT)) == len(events)


def send_text(text):
    """Type text as characters, the same whatever the keyboard layout. False if refused.

    Sent as UTF-16 code units, which is what a key event carries: a character outside the basic
    plane is two of them.
    """
    units = text.encode("utf-16-le")
    events = []
    for i in range(0, len(units), 2):
        code = units[i] | (units[i + 1] << 8)
        events += [_key_event(scan=code, flags=KEYEVENTF_UNICODE),
                   _key_event(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return _send(events)


def send_keys(*vks):
    """Press keys together, then release in reverse, as a person holds Ctrl and taps S."""
    return _send([_key_event(vk=vk) for vk in vks]
                 + [_key_event(vk=vk, flags=KEYEVENTF_KEYUP) for vk in reversed(vks)])


def tap_key(vk, times=1):
    return _send([_key_event(vk=vk), _key_event(vk=vk, flags=KEYEVENTF_KEYUP)] * times)


def parse_keys(spoken):
    """The virtual keys a spoken chord names, modifiers first: "control shift t", "alt f4".

    None unless it is modifiers followed by at most one key, letter or digit.
    """
    words = spoken.lower().replace("+", " ").replace("-", " ").split()
    keys = []
    while words and words[0] in MODIFIERS:
        keys.append(MODIFIERS[words.pop(0)][0])

    key = re.sub(r"^f (\d+)$", r"f\1", " ".join(words))   # "F 5" -> "f5"
    if key in KEYS:
        keys.append(KEYS[key])
    elif len(key) == 1 and key.isascii() and key.isalnum():
        keys.append(ord(key.upper()))
    elif key or not keys:
        return None
    return tuple(keys)


def hotkey(spec, callback):
    """Call callback, on a thread of its own, whenever the key combination spec is pressed.

    False when spec is not modifiers plus one key, or another program already owns it.
    """
    words = spec.lower().replace("+", " ").split()
    flags = 0
    while words and words[0] in MODIFIERS:
        flags |= MODIFIERS[words.pop(0)][1]
    key = parse_keys(" ".join(words)) if words else None
    if not flags or key is None or len(key) != 1:
        return False

    registered = threading.Event()
    result = []

    def listen():
        # The hotkey belongs to the thread that registers it, and arrives in its message queue.
        result.append(bool(user32.RegisterHotKey(None, 1, flags | MOD_NOREPEAT, key[0])))
        registered.set()
        message = w.MSG()
        while result[0] and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                callback()

    threading.Thread(target=listen, daemon=True, name="hotkey").start()
    registered.wait(2)
    return bool(result and result[0])


# -- everything else -------------------------------------------------------------


def friendly_username():
    """The Windows account name when it reads like a real name ("marko-kg102" does not), else ""."""
    name = os.environ.get("USERNAME", "").strip()
    return name if name.isalpha() and 2 <= len(name) <= 20 else ""


def is_elevated():
    """Whether Hard2Assist is running as administrator."""
    return bool(shell32.IsUserAnAdmin())


def clipboard_text():
    """The text on the clipboard, or ""."""
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        pointer = kernel32.GlobalLock(handle) if handle else None
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def known_folder(guid):
    """Where a Windows known folder really is, or "".

    Asked of Windows because Documents and Pictures are routinely redirected into OneDrive.
    `guid` is the folder's id as its braced string.
    """
    parsed = _GUID()
    if ole32.CLSIDFromString(guid, ctypes.byref(parsed)) != 0:
        return ""

    path = ctypes.c_wchar_p()
    try:
        if shell32.SHGetKnownFolderPath(ctypes.byref(parsed), 0, None, ctypes.byref(path)) != 0:
            return ""
        return path.value or ""
    finally:
        ole32.CoTaskMemFree(path)   # Windows allocated it, even on failure
