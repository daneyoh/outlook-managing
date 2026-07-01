"""Create a desktop shortcut for the Outlook mail widget."""
import os
import sys

try:
    import win32com.client
except ImportError:
    # fallback: use VBScript
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    vbs = os.path.join(desktop, "_make_shortcut.vbs")
    here = os.path.dirname(os.path.abspath(__file__))
    pyw = os.path.join(os.environ["LOCALAPPDATA"],
                       "Programs", "Python", "Python313", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = os.path.join(os.environ["LOCALAPPDATA"],
                           "Programs", "Python", "Python312", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = "pythonw.exe"
    ico = os.path.join(os.path.dirname(here), "widget.ico")
    lnk = os.path.join(desktop, "Outlook Mail Widget.lnk")

    script = f'''Set ws = CreateObject("WScript.Shell")
Set sc = ws.CreateShortcut("{lnk}")
sc.TargetPath = "{pyw}"
sc.Arguments = "app.py"
sc.WorkingDirectory = "{here}"
sc.IconLocation = "{ico}"
sc.Description = "Outlook Mail Widget"
sc.Save
WScript.Echo "OK"
'''
    with open(vbs, "w", encoding="utf-8") as f:
        f.write(script)
    os.system(f'cscript //nologo "{vbs}"')
    os.remove(vbs)
    print(f"Shortcut created: {lnk}")
    sys.exit(0)

# win32com available
desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
here = os.path.dirname(os.path.abspath(__file__))
pyw = os.path.join(os.environ["LOCALAPPDATA"],
                   "Programs", "Python", "Python313", "pythonw.exe")
if not os.path.exists(pyw):
    pyw = os.path.join(os.environ["LOCALAPPDATA"],
                       "Programs", "Python", "Python312", "pythonw.exe")
if not os.path.exists(pyw):
    pyw = "pythonw.exe"

ws = win32com.client.Dispatch("WScript.Shell")
lnk = os.path.join(desktop, "Outlook Mail Widget.lnk")
sc = ws.CreateShortcut(lnk)
sc.TargetPath = pyw
sc.Arguments = "app.py"
sc.WorkingDirectory = here
sc.IconLocation = os.path.join(os.path.dirname(here), "widget.ico")
sc.Description = "Outlook Mail Widget"
sc.Save()
print(f"Shortcut created: {lnk}")
