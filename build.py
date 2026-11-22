"""Build Hard2Assist.

    python build.py               # dist/Hard2Assist/ -- the app folder
    python build.py --installer   # ...and wrap it in installer/Hard2Assist-Setup.exe

A folder with the .exe and the Python runtime beside it, not a single self-extracting .exe: that
unpacks the whole bundle into %TEMP% on every launch, which costs seconds and looks to antivirus
like a dropper. The installer built from the folder is the single file to hand out.

The speech model and the voice are not bundled: the app downloads them on first launch.
"""

import ast
import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import time

from version import AUTHOR, NAME, VERSION

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = "H2A.ico"
VERSION_FILE = "version_info.txt"
INSTALLER_SCRIPT = "installer.iss"

# Modules PyInstaller would find but that never run. requests, tqdm and filelock must stay:
# Moonshine's downloader uses all three on first launch. comtypes.tools must stay too: it builds
# the COM wrappers the volume control and the Store app list need, on first use.
EXCLUDES = ["tkinter", "setuptools", "distutils", "pkg_resources", "PIL", "yaml", "matplotlib",
            "PyQt5", "PyQt6", "unittest", "pydoc", "pytest", "speech_recognition"]

# Moonshine's package holds 8 MB of sample recordings and a test model; only its two beeps are used.
_MOONSHINE = os.path.dirname(importlib.util.find_spec("moonshine_voice").origin) \
    if importlib.util.find_spec("moonshine_voice") else ""
BEEPS = [os.path.join(_MOONSHINE, "assets", name) for name in ("success.wav", "error.wav")]

# Parts of Qt collected for features the dock never uses, deleted after the build: the software
# OpenGL fallback (20 MB; the dock paints without OpenGL), Qt's own translations, platform plugins
# other than Windows', and networking plugins (downloads go through Python, not Qt).
UNUSED = ["PySide6/opengl32sw.dll", "PySide6/translations", "PySide6/plugins/tls",
          "PySide6/plugins/networkinformation", "PySide6/plugins/platforms/qdirect2d.dll",
          "PySide6/plugins/platforms/qminimal.dll", "PySide6/plugins/platforms/qoffscreen.dll"]

OPTIONS = [
    "--onedir",
    "--windowed",        # no console window behind the app
    "--name", NAME,
    "--noconfirm",
    "--noupx",           # packed executables are heavily associated with malware
    # A publisher, description and version make the .exe less anonymous to SmartScreen.
    "--version-file", VERSION_FILE,
    "--icon", ICON,
    "--add-data", f"{ICON}{os.pathsep}.",   # for the running window's own icon
    # Commands are found on disk at runtime, so they ship as data; what they import is added by
    # command_imports() below.
    "--add-data", f"commands{os.pathsep}commands",
    # Volume and the Store app list talk to Windows over COM; comtypes.gen is generated at runtime.
    "--hidden-import", "comtypes",
    "--hidden-import", "comtypes.stream",
    "--hidden-import", "comtypes.client",
    "--hidden-import", "comtypes.gen",
    "--hidden-import", "pycaw.utils",
    # moonshine.dll and the onnxruntime.dll it loads from beside itself.
    "--collect-binaries", "moonshine_voice",
]
for beep in BEEPS:
    OPTIONS += ["--add-data", f"{beep}{os.pathsep}moonshine_voice/assets"]
for module in EXCLUDES:
    OPTIONS += ["--exclude-module", module]


def command_imports():
    """--hidden-import for everything the command files import.

    PyInstaller cannot see the commands, so it cannot see their imports either, and a module
    missed here gives a build that starts fine but silently loads fewer commands.
    """
    found = set()
    for path in glob.glob(os.path.join(HERE, "commands", "*", "*.py")):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):   # imports inside functions too
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                found.add(node.module)

    return [option for module in sorted(found) for option in ("--hidden-import", module)]


# The .exe's version resource. Both version fields need four numbers.
VERSION_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({parts}), prodvers=({parts}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{publisher}'),
      StringStruct('FileDescription', '{name} -- Windows voice assistant'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def write_version_file():
    parts = (tuple(int(n) for n in VERSION.split(".")) + (0, 0, 0))[:4]
    with open(os.path.join(HERE, VERSION_FILE), "w", encoding="utf-8") as f:
        f.write(VERSION_TEMPLATE.format(parts=", ".join(map(str, parts)), version=".".join(map(str, parts)),
                                        publisher=AUTHOR, name=NAME))


def folder_size(folder):
    return sum(os.path.getsize(os.path.join(root, name))
               for root, _dirs, files in os.walk(folder) for name in files)


def prune(app_dir):
    """Delete what UNUSED names. Returns the bytes freed."""
    freed = 0
    for relative in UNUSED:
        path = os.path.join(app_dir, "_internal", *relative.split("/"))
        if os.path.isdir(path):
            freed += folder_size(path)
            shutil.rmtree(path)
        elif os.path.isfile(path):
            freed += os.path.getsize(path)
            os.remove(path)
    return freed


def find_inno():
    """Inno Setup's compiler, or None. It does not add itself to PATH, and installs either for
    everyone or for one user."""
    found = shutil.which("ISCC")
    if found:
        return found
    for base in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
                 os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", "")):
        for version in ("Inno Setup 6", "Inno Setup 5"):
            path = os.path.join(base, version, "ISCC.exe")
            if base and os.path.isfile(path):
                return path
    return None


def build_installer(app_dir):
    compiler = find_inno()
    if compiler is None:
        print("\nInno Setup is not installed, so no installer was built.")
        print("Get it from https://jrsoftware.org/isdl.php (free, no account)")
        print("and run: python build.py --installer")
        return None

    result = subprocess.run([compiler, f"/DAppName={NAME}", f"/DAppPublisher={AUTHOR}",
                             f"/DAppVersion={VERSION}", f"/DAppSource={app_dir}",
                             os.path.join(HERE, INSTALLER_SCRIPT)], cwd=HERE)
    return os.path.join(HERE, "installer", f"{NAME}-Setup.exe") if result.returncode == 0 else None


# Windows keeps a folder locked while anything looks at it -- the app just closed, an Explorer
# window, a terminal inside it -- usually for under a second.
CLEAN_ATTEMPTS = 8
CLEAN_PAUSE = 0.5


def clean(path):
    """Delete a previous build folder. False, having said why, if Windows would not let go."""
    blocked = None
    for _ in range(CLEAN_ATTEMPTS):
        if not os.path.isdir(path):
            return True
        try:
            shutil.rmtree(path)
            return True
        except PermissionError as e:
            blocked = e
            time.sleep(CLEAN_PAUSE)

    print(f"\nCould not delete {path}\n({blocked})")
    print(f"\nSomething has that folder open. Usually it is the app itself -- close {NAME} if it is")
    print("still running. Otherwise it is an Explorer window showing the folder, or a terminal")
    print("sitting inside it.")
    return False


def main():
    # The PyInstaller of the Python running this, so the build uses this environment's packages.
    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is not installed. Run: pip install -r requirements-build.txt")
        return 1
    if not _MOONSHINE:
        print("moonshine-voice is not installed. Run: pip install -r requirements-build.txt")
        return 1
    if not os.path.isfile(os.path.join(HERE, ICON)):
        print(f"{ICON} is missing -- the .exe would get the default icon.")
        return 1

    for stale in ("build", "dist", "installer"):
        if not clean(os.path.join(HERE, stale)):
            return 1
    write_version_file()

    result = subprocess.run([sys.executable, "-m", "PyInstaller", *OPTIONS, *command_imports(),
                             "hard2assist.py"], cwd=HERE)
    if result.returncode != 0:
        return result.returncode

    app_dir = os.path.join(HERE, "dist", NAME)
    if not os.path.isfile(os.path.join(app_dir, f"{NAME}.exe")):
        print(f"\nThe build finished but {NAME}.exe is missing.")
        return 1

    freed = prune(app_dir)
    print(f"\nRemoved {freed / 1024 ** 2:.0f} MB of unused Qt parts.")
    print(f"\nBuilt {app_dir} ({folder_size(app_dir) / 1024 ** 2:.0f} MB)")
    print("Open Hard2Assist.exe inside it and type `help` into the dock -- seeing every command")
    print("listed is how you know nothing was excluded by mistake.")

    if "--installer" in sys.argv:
        setup = build_installer(app_dir)
        if setup is None:
            return 1
        print(f"\nBuilt {setup} ({os.path.getsize(setup) / 1024 ** 2:.0f} MB)")
        print("That single file is what users download.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
