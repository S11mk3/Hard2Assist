"""Build Hard2Assist.exe.

    python build.py

Produces dist/Hard2Assist.exe: a single file with Python and every library
bundled inside, so it runs on a Windows PC with nothing installed.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ICON = "H2A.ico"

OPTIONS = [
    "--onefile",              # a single .exe rather than a folder of files
    "--windowed",             # no console window behind the app
    "--name", "Hard2Assist",
    "--noconfirm",

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
]


def main():
    if shutil.which("pyinstaller") is None:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

    if not os.path.isfile(os.path.join(HERE, ICON)):
        print(f"{ICON} is missing -- the .exe would get the default icon.")
        return 1

    # Remove stale build output so the result is a clean, full rebuild.
    for stale in ("build", "dist"):
        path = os.path.join(HERE, stale)
        if os.path.isdir(path):
            shutil.rmtree(path)

    result = subprocess.run(
        ["pyinstaller", *OPTIONS, "hard2assist.py"],
        cwd=HERE,
    )
    if result.returncode != 0:
        return result.returncode

    exe = os.path.join(HERE, "dist", "Hard2Assist.exe")
    size = os.path.getsize(exe) / (1024 * 1024)
    print(f"\nBuilt {exe} ({size:.0f} MB)")
    print("Copy that one file anywhere -- it needs nothing else installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
