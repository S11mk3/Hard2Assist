import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from commands.SystemApps.Open import app_map


def run():
    print("\nList of commands:")
    print(" computer open\n"
          "computer close\n"
          "computer kill(same function as close)\n"
          "computer help\n" 
          "computer stop\n")

    print("List of system aplications that you can open and close: \n")

    exclude = {"calc", "explorer", "taskmgr", "task manger",
               "power", "device manger", "device man", "disk managment",
               "disc managment", "performance mon", "computer managment",
               "computer manger"}
    
    apps = [app for app in app_map if app not in exclude] 
    width = 25  # column width

    for i in range(0, len(apps), 4):
        row = apps[i:i+4]
        print("".join(app.ljust(width) for app in row))

    print()