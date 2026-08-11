"""Build Hard2Assist.

    python build.py               # dist/Hard2Assist/ -- the app folder
    python build.py --installer   # ...and wrap it in Hard2Assist-Setup.exe

Produces a folder containing the .exe and the Python runtime beside it, rather
than a single self-extracting .exe. The one-file build unpacked ~67 MB into
%TEMP% on *every* launch, which cost seconds of startup and made the app look
like a dropper to antivirus heuristics -- a process that writes executables to
a temp folder and runs them. A plain folder starts immediately and behaves
like ordinary installed software.

What users download is the installer built from that folder, so the "one file
to download" property survives the change.
"""

import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

ICON = "H2A.ico"
NAME = "Hard2Assist"
PUBLISHER = "Andrija Simic"

# Single source of truth for the version: it is written into the .exe's
# resource block below and handed to the installer script, so a release only
# needs the number changed here.
VERSION = "1.0.0"

VERSION_FILE = "version_info.txt"
INSTALLER_SCRIPT = "installer.iss"

# Modules PyInstaller finds by static analysis but that never run.
#
# SpeechRecognition supports a dozen recognisers and PyInstaller cannot tell
# which one is actually called, so it packs the dependencies of all of them.
# Hard2Assist uses exactly two things from that library -- sr.Microphone and
# recognize_google -- and both are pure standard library underneath
# (urllib, wave, audioop, aifc). Nothing on that path imports any of the
# following, so excluding them cannot break recognition:
#
#   numpy       reached only from recognizers/whisper_local/, and there only
#               inside `if TYPE_CHECKING:` -- it is never imported at runtime,
#               yet it was the single largest thing in the bundle
#   requests    with h2/hpack/hyperframe behind it; the Google recogniser uses
#               urllib.request instead
#   pocketsphinx, yaml, PIL     other optional recognisers and their baggage
#   setuptools, distutils, pkg_resources    build-time tooling
#   unittest, pydoc, pytest     development-only
#
# Do NOT add comtypes.tools here. It looks like dead weight but generates the
# SAPI typelib wrapper on first run, and without it the voice never starts.
EXCLUDES = [
    "numpy",
    "setuptools",
    "distutils",
    "pkg_resources",
    "PIL",
    "yaml",
    "requests",
    "h2",
    "hpack",
    "hyperframe",
    "pocketsphinx",
    "unittest",
    "pydoc",
    "pytest",
]

# Data that PyInstaller collects because it sits inside a package directory.
# --exclude-module cannot reach any of it: these are not imports, they are
# files, so they have to be deleted after the build.
#
#   pocketsphinx-data   the offline CMU Sphinx English models, and by a wide
#                       margin the largest thing in the bundle at 38 MB -- a
#                       28 MB language model alone. Only recognize_sphinx()
#                       reads it, and Hard2Assist uses recognize_google().
#   flac-linux/flac-mac SpeechRecognition ships a FLAC encoder per platform.
#                       flac-win32.exe must stay -- every clip is encoded
#                       through it before upload -- but Linux and macOS
#                       executables inside a Windows app are pure weight, and
#                       embedded foreign binaries give a scanner one more
#                       thing to dislike.
UNUSED_PAYLOAD = ("pocketsphinx-data", "flac-linux", "flac-mac")

OPTIONS = [
    "--onedir",               # a folder; see the module docstring
    "--windowed",             # no console window behind the app
    "--name", NAME,
    "--noconfirm",

    # UPX compression is off deliberately. Packed executables are heavily
    # associated with malware, and compressing an app that no longer unpacks
    # itself at startup buys nothing anyway.
    "--noupx",

    # An .exe with no publisher, description or version reads as anonymous to
    # SmartScreen and to antivirus reputation scoring.
    "--version-file", VERSION_FILE,

    # The icon for the .exe file itself...
    "--icon", ICON,
    # ...and a copy inside the bundle, because the running window sets its
    # own title bar and taskbar icon from the file at runtime.
    "--add-data", f"{ICON}{os.pathsep}.",

    # Command modules are discovered by scanning the disk at runtime, so
    # PyInstaller cannot see their imports and would omit them. The folder is
    # shipped as data; registry.py knows to look for it inside the bundle.
    "--add-data", f"commands{os.pathsep}commands",

    # Because the command modules are invisible to PyInstaller, so is
    # everything they import. Without these hidden imports the build succeeds
    # but the .exe loads almost no commands. After changing this list, run
    # the built .exe and check `computer help` still shows every command --
    # a build missing a piece starts up looking fine.
    "--hidden-import", "apps",
    "--hidden-import", "win",
    "--hidden-import", "psutil",
    "--hidden-import", "speech",

    # Speech and volume both talk to Windows over COM.
    "--hidden-import", "comtypes",
    "--hidden-import", "comtypes.stream",
    "--hidden-import", "comtypes.client",
    "--hidden-import", "comtypes.gen",

    # Reached only from command modules, which PyInstaller cannot see.
    "--hidden-import", "audio",
    "--hidden-import", "pycaw",
    "--hidden-import", "pycaw.utils",
    "--hidden-import", "session",
    "--hidden-import", "spoken",
    "--hidden-import", "listener",
]

for module in EXCLUDES:
    OPTIONS += ["--exclude-module", module]


# The Windows version resource. Both version fields have to be four numbers,
# so the VERSION above is padded out to build 0.
VERSION_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({parts}),
    prodvers=({parts}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{publisher}'),
          StringStruct('FileDescription', 'Hard2Assist -- Windows voice assistant'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', '{name}'),
          StringStruct('OriginalFilename', '{name}.exe'),
          StringStruct('ProductName', '{name}'),
          StringStruct('ProductVersion', '{version}'),
        ],
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def write_version_file():
    """Write the resource file PyInstaller stamps into the .exe."""
    parts = tuple(int(n) for n in VERSION.split("."))
    parts += (0,) * (4 - len(parts))

    text = VERSION_TEMPLATE.format(
        parts=", ".join(str(n) for n in parts),
        version=".".join(str(n) for n in parts),
        publisher=PUBLISHER,
        name=NAME,
    )

    with open(os.path.join(HERE, VERSION_FILE), "w", encoding="utf-8") as f:
        f.write(text)


def strip_unused_payload(folder):
    """Delete the collected data listed in UNUSED_PAYLOAD.

    Returns how many bytes it freed. Walks bottom-up so a directory is only
    considered after its contents have been measured.
    """
    freed = 0

    for root, dirs, files in os.walk(folder, topdown=False):
        for name in files:
            if name.startswith(UNUSED_PAYLOAD):
                path = os.path.join(root, name)
                freed += os.path.getsize(path)
                os.remove(path)

        for name in dirs:
            if name.startswith(UNUSED_PAYLOAD):
                path = os.path.join(root, name)
                freed += folder_size(path)
                shutil.rmtree(path)

    return freed


def folder_size(folder):
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def find_inno():
    """The Inno Setup command line compiler, or None if it is not installed.

    Inno Setup does not add itself to PATH, and it can be installed either for
    everyone (Program Files) or for one user (%LOCALAPPDATA%\\Programs), so
    all three places are worth a look before giving up.
    """
    found = shutil.which("ISCC")
    if found:
        return found

    bases = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        os.environ.get("PROGRAMFILES(X86)", ""),
        os.environ.get("PROGRAMFILES", ""),
    ]

    for base in bases:
        if not base:
            continue
        for version in ("Inno Setup 6", "Inno Setup 5"):
            path = os.path.join(base, version, "ISCC.exe")
            if os.path.isfile(path):
                return path

    return None


def build_installer(app_dir):
    """Compile installer.iss into Hard2Assist-Setup.exe. Returns its path."""
    compiler = find_inno()

    if compiler is None:
        print("\nInno Setup is not installed, so no installer was built.")
        print("Get it from https://jrsoftware.org/isdl.php (free, no account)")
        print("and run: python build.py --installer")
        return None

    result = subprocess.run(
        [
            compiler,
            f"/DAppVersion={VERSION}",
            f"/DAppSource={app_dir}",
            os.path.join(HERE, INSTALLER_SCRIPT),
        ],
        cwd=HERE,
    )
    if result.returncode != 0:
        return None

    return os.path.join(HERE, "installer", f"{NAME}-Setup.exe")


# How long to keep trying to delete the previous build.
#
# Windows holds a folder open for as long as anything is looking at it, and the
# ordinary way to hit that is to rebuild straight after testing: the .exe has
# only just exited, or the folder is still showing in an Explorer window. The
# handle is usually released within a second, so retrying turns what was a
# traceback halfway through the delete into a pause nobody notices.
CLEAN_ATTEMPTS = 8
CLEAN_PAUSE = 0.5


def clean(path):
    """Delete a previous build folder. False if Windows would not let go.

    Reported rather than raised, because "the app you were just testing is
    still running" is a normal thing to have done and deserves a sentence
    saying so, not a stack trace ending in WinError 32.
    """
    blocked = None

    for _ in range(CLEAN_ATTEMPTS):
        if not os.path.isdir(path):
            return True

        try:
            shutil.rmtree(path)
            return True
        except PermissionError as e:
            # A partial delete: rmtree removes what it can and stops at the
            # first locked entry, so the next attempt has less left to do.
            blocked = e
            time.sleep(CLEAN_PAUSE)

    print(f"\nCould not delete {path}")
    print(f"({blocked})")
    print("\nSomething has that folder open. Usually it is the app itself --")
    print(f"close {NAME} if it is still running. Otherwise it is an Explorer")
    print("window showing the folder, or a terminal sitting inside it; a")
    print("folder cannot be deleted while anything is looking at it.")

    return False


def main():
    if shutil.which("pyinstaller") is None:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

    if not os.path.isfile(os.path.join(HERE, ICON)):
        print(f"{ICON} is missing -- the .exe would get the default icon.")
        return 1

    # Remove stale build output so the result is a clean, full rebuild.
    for stale in ("build", "dist", "installer"):
        if not clean(os.path.join(HERE, stale)):
            return 1

    write_version_file()

    result = subprocess.run(
        ["pyinstaller", *OPTIONS, "hard2assist.py"],
        cwd=HERE,
    )
    if result.returncode != 0:
        return result.returncode

    app_dir = os.path.join(HERE, "dist", NAME)
    exe = os.path.join(app_dir, f"{NAME}.exe")

    if not os.path.isfile(exe):
        print(f"\nThe build finished but {exe} is missing.")
        return 1

    freed = strip_unused_payload(app_dir)
    if freed:
        print(f"\nRemoved {freed / (1024 * 1024):.0f} MB of unused bundled data.")

    print(f"\nBuilt {app_dir} ({folder_size(app_dir) / (1024 * 1024):.0f} MB)")
    print("Open Hard2Assist.exe inside it and say `computer help` -- seeing every")
    print("command listed is how you know nothing was excluded by mistake.")

    if "--installer" in sys.argv:
        setup = build_installer(app_dir)
        if setup is None:
            return 1
        print(f"\nBuilt {setup} ({os.path.getsize(setup) / (1024 * 1024):.0f} MB)")
        print("That single file is what users download.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
