#importing needed libraries
import subprocess
import time
import ctypes
import json

#list of system apps and programms
app_map = {
    "calculator": "calc",
    "calc": "calc",

    "file explorer": "explorer",
    "explorer": "explorer",

    "notepad": "notepad",

    "paint": "mspaint",

    "wordpad": "write",

    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "task manger": "taskmgr",

    "command prompt": "cmd",
    "cmd": "cmd",

    "powershell": "powershell",
    "power": "powershell",

    "settings": "ms-settings:",

    "control panel": "control",
    "control pan": "control",

    "device manager": "devmgmt.msc",
    "device manger": "devmgmt.msc",
    "device man": "devmgmt.msc", 

    "disk management": "diskmgmt.msc",
    "disk managment": "diskmgmt.msc",
    "disc managment": "diskmgmt.msc",

    "services": "services.msc",

    "regedit": "regedit",

    "system information": "msinfo32",

    "resource monitor": "resmon",

    "performance monitor": "perfmon",
    "performance mon": "perfmon",

    "event viewer": "eventvwr",

    "computer management": "compmgmt.msc",
    "computer managment": "compmgmt.msc",  
    "computer manger": "compmgmt.msc",  

    "user account": "netplwiz",
    "user accounts": "netplwiz",

    "snipping tool": "snippingtool",
    "screenshot": "snippingtool",

    "media player": "wmplayer",

    "narrator": "narrator",

    "magnifier": "magnify",

    "on screen keyboard": "osk",

    "edge": "msedge",

    "internet explorer": "iexplore",
    
    "vlc": "vlc",
}



user32 = ctypes.windll.user32
opened_windows = []

def get_active_window():
    return user32.GetForegroundWindow()


def run(name):
    name = name.lower().strip()
    app = app_map.get(name, name)

    before = get_active_window()

    try:
        subprocess.run(f'start "" "{app}"', shell=True)
        print(f"Opening {name}...")
    except Exception as e:
        print(f"Error opening {name}: {e}")
        return

    time.sleep(1.5)

    after = get_active_window()

    if after != before:
        opened_windows.append((name, after))

    with open("windows.json", "w") as f:
        json.dump(opened_windows, f)