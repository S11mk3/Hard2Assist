"""Build Hard2Assist.

    python build.py               # dist/Hard2Assist/ -- the app folder
    python build.py --installer   # ...and wrap it in Hard2Assist-Setup.exe
    python build.py --fetch-model # only download the speech model into models/,
                                  # which running from source needs too

Produces a folder containing the .exe with the Python runtime beside it,
rather than a single self-extracting .exe. A one-file build unpacks the whole
bundle into %TEMP% on every launch, which costs seconds of startup and looks
to antivirus heuristics like a dropper. What users download is the installer
built from that folder, so the single file to hand out still exists.
"""

import ast
import glob
import os
import shutil
import subprocess
import sys
import time

# The version lives in version.py, which the app reads too. It is written into
# the .exe's resource block below and handed to the installer script.
from version import AUTHOR as PUBLISHER
from version import NAME, VERSION

# The speech model's folder name under models/, shared with the app.
from recognizer import MODEL

HERE = os.path.dirname(os.path.abspath(__file__))

ICON = "H2A.ico"

VERSION_FILE = "version_info.txt"
INSTALLER_SCRIPT = "installer.iss"

# Modules PyInstaller finds by static analysis but that never run.
#
# SpeechRecognition supports a dozen recognisers and PyInstaller cannot tell
# which one is called, so it packs the dependencies of all of them.
# Hard2Assist uses sr.Microphone, Moonshine's Transcriber (recognizer.py) and
# recognize_google as the fallback. The first and last are pure standard
# library underneath (urllib, wave, audioop, aifc), and the Transcriber is a
# native library reached through ctypes. Nothing on that path imports any of
# the following:
#
#   numpy       reached only from recognizers/whisper_local/, and there only
#               inside `if TYPE_CHECKING:`, and from Moonshine's own
#               microphone class, which Hard2Assist does not use
#   requests    with h2/hpack/hyperframe behind it; the Google recogniser uses
#               urllib.request instead
#   sounddevice, tqdm, filelock     Moonshine's microphone capture and model
#               downloader. The app captures audio itself, and the model is
#               bundled rather than downloaded
#   pocketsphinx, yaml, PIL     other optional recognisers and their baggage
#   vosk        the offline recogniser, when installed. Through tqdm.gui it
#               drags in matplotlib and a Qt binding (PySide6): 110 MB
#   matplotlib, PySide6, shiboken6, PyQt5, PyQt6    that same baggage, named
#               outright so no other route can bring it back
#   setuptools, distutils, pkg_resources    build-time tooling
#   unittest, pydoc, pytest     development-only
#
# comtypes.tools does not belong here. It looks like dead weight but generates
# the SAPI typelib wrapper on first run, and without it the voice never starts.
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
    "sounddevice",
    "tqdm",
    "filelock",
    "pocketsphinx",
    "vosk",
    "matplotlib",
    "PySide6",
    "shiboken6",
    "PyQt5",
    "PyQt6",
    "unittest",
    "pydoc",
    "pytest",
]

# Data PyInstaller collects because it sits inside a package directory.
# --exclude-module cannot reach any of it: these are files, not imports, so
# they are deleted after the build.
#
#   pocketsphinx-data   the offline CMU Sphinx English models, 38 MB of which
#                       28 MB is one language model. Only recognize_sphinx()
#                       reads it, and Hard2Assist uses Moonshine instead.
#   flac-linux/flac-mac SpeechRecognition ships a FLAC encoder per platform.
#                       flac-win32.exe must stay -- the Google fallback
#                       encodes every clip through it before upload -- but
#                       the Linux and macOS executables are weight a Windows
#                       app cannot use.
UNUSED_PAYLOAD = ("pocketsphinx-data", "flac-linux", "flac-mac")

OPTIONS = [
    "--onedir",               # a folder; see the module docstring
    "--windowed",             # no console window behind the app
    "--name", NAME,
    "--noconfirm",

    # Packed executables are heavily associated with malware, and a folder
    # build has nothing to gain from compression anyway.
    "--noupx",

    # An .exe with no publisher, description or version reads as anonymous to
    # SmartScreen and to antivirus reputation scoring.
    "--version-file", VERSION_FILE,

    # The icon for the .exe file itself...
    "--icon", ICON,
    # ...and a copy inside the bundle, which the running window reads to set
    # its own title bar and taskbar icon.
    "--add-data", f"{ICON}{os.pathsep}.",

    # Command modules are discovered by scanning the disk at runtime, so
    # PyInstaller cannot see their imports and would omit them. The folder
    # ships as data; registry.py knows to look for it inside the bundle.
    # What the commands import is added by command_imports() below.
    "--add-data", f"commands{os.pathsep}commands",

    # Speech and volume both talk to Windows over COM. comtypes.gen is
    # generated at runtime, so no import of it exists for anything to find.
    "--hidden-import", "comtypes",
    "--hidden-import", "comtypes.stream",
    "--hidden-import", "comtypes.client",
    "--hidden-import", "comtypes.gen",
    "--hidden-import", "pycaw.utils",

    # Moonshine's native library. moonshine.dll is loaded by path from beside
    # the package, and needs the onnxruntime.dll next to it, so both go into
    # the bundle's moonshine_voice folder. The package's assets folder --
    # sample recordings and a tiny model -- is left out.
    "--collect-binaries", "moonshine_voice",

    # The speech model itself; recognizer.model_dir() reads it from here.
    "--add-data", f"{os.path.join('models', MODEL)}{os.pathsep}models/{MODEL}",
]

for module in EXCLUDES:
    OPTIONS += ["--exclude-module", module]


def command_imports():
    """Every module the command files import, as --hidden-import options.

    Because the command modules are invisible to PyInstaller, so is everything
    they import, and a module missed here gives a build that starts and looks
    fine but silently loads fewer commands. Reading the imports straight out
    of the files means a new command, or a new import in one, needs no change
    here.
    """
    found = set()

    for path in glob.glob(os.path.join(HERE, "commands", "*", "*.py")):
        # Skipped by registry.py too, so never loaded.
        if os.path.basename(path).startswith("_"):
            continue

        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)

        # ast.walk reaches imports inside functions as well as at the top.
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                found.add(node.module)

    options = []
    for module in sorted(found):
        options += ["--hidden-import", module]
    return options


# The Windows version resource. Both version fields have to be four numbers,
# so VERSION above is padded out to build 0.
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

    Returns how many bytes it freed. Walks bottom-up, so a directory is only
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
    """Total size in bytes of everything under a folder."""
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def fetch_model():
    """Put the speech model in models/, downloading it the first time.

    Returns its folder, or None if it could not be fetched. Moonshine's own
    downloader keeps a cache in %LOCALAPPDATA%\\moonshine_voice, so a second
    fetch is a copy rather than a download. models/ is not in git: 139 MB of
    weights belongs in the build, not in the repository.
    """
    target = os.path.join(HERE, "models", MODEL)
    if os.path.isdir(target) and os.listdir(target):
        return target

    try:
        from moonshine_voice import ModelArch, get_model_for_language
    except ImportError:
        print("moonshine-voice is not installed. Run: "
              "pip install -r requirements.txt")
        return None

    print(f"Fetching the speech model ({MODEL})...")
    try:
        source, _arch = get_model_for_language("en", ModelArch.SMALL_STREAMING)
    except Exception as e:
        print(f"Could not download the speech model: {e}")
        return None

    shutil.copytree(source, target)
    print(f"Speech model ready in {target}")
    return target


def find_inno():
    """The Inno Setup command line compiler, or None if it is not installed.

    Inno Setup does not add itself to PATH, and it installs either for
    everyone (Program Files) or for one user (%LOCALAPPDATA%\\Programs), so
    all three places are checked.
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
# Windows holds a folder open for as long as anything is looking at it, which
# a rebuild straight after testing runs into: the .exe has only just exited,
# or the folder is still showing in an Explorer window. The handle is usually
# released within a second.
CLEAN_ATTEMPTS = 8
CLEAN_PAUSE = 0.5


def clean(path):
    """Delete a previous build folder. False if Windows would not let go.

    Reported rather than raised: "the app you were just testing is still
    running" deserves a sentence saying so, not a stack trace.
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
    """Build the app folder, and the installer when asked."""
    if "--fetch-model" in sys.argv:
        return 0 if fetch_model() else 1

    if shutil.which("pyinstaller") is None:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

    if not os.path.isfile(os.path.join(HERE, ICON)):
        print(f"{ICON} is missing -- the .exe would get the default icon.")
        return 1

    # Bundled rather than downloaded on first run, so the installed app works
    # offline from the start.
    if fetch_model() is None:
        return 1

    # Remove stale output so the result is a clean, full rebuild.
    for stale in ("build", "dist", "installer"):
        if not clean(os.path.join(HERE, stale)):
            return 1

    write_version_file()

    result = subprocess.run(
        ["pyinstaller", *OPTIONS, *command_imports(), "hard2assist.py"],
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
