"""Build Hard2Assist.exe.

    python build.py

Produces dist/Hard2Assist.exe -- a single file with Python and every library
inside it, so it runs on a Windows PC with nothing installed.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

OPTIONS = [
    "--onefile",              # one .exe rather than a folder of files
    "--windowed",             # no console window behind the app
    "--name", "Hard2Assist",
    "--noconfirm",

    # The commands/ folder is found by scanning at runtime, so PyInstaller
    # cannot see those imports and would leave them out. Ship the folder as
    # data; registry.py knows to look for it inside the bundle.
    "--add-data", f"commands{os.pathsep}commands",

    # ...and because those command modules are invisible to PyInstaller, so is
    # everything *they* import. Without these the .exe builds happily and then
    # loads only `stop`, because apps/win/psutil were never packed. Do not
    # remove these without running `--selftest` on the result.
    "--hidden-import", "apps",
    "--hidden-import", "win",
    "--hidden-import", "psutil",
]


def main():
    if shutil.which("pyinstaller") is None:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

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
