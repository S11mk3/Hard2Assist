import json
import ctypes

user32 = ctypes.windll.user32

def run(name):
    name = name.lower().strip()

    try:
        with open("windows.json", "r") as f:
            opened_windows = json.load(f)
    except:
        print("No tracking file found")
        return

    for i in range(len(opened_windows) - 1, -1, -1):
        app_name, hwnd = opened_windows[i]

        if app_name == name:
            hwnd = int(hwnd)

            if user32.IsWindow(hwnd):
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
                print(f"Closed {name}")
            else:
                print(f"{name} already closed")

            opened_windows.pop(i)

            with open("windows.json", "w") as f:
                json.dump(opened_windows, f)

            return

    print(f"No tracked window for {name}")
