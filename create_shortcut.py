import os, pathlib

# Use OneDrive Desktop if it exists, otherwise standard Desktop
onedrive_desktop = pathlib.Path.home() / "OneDrive - Novamodus Inc" / "Desktop"
standard_desktop = pathlib.Path.home() / "Desktop"
desktop = onedrive_desktop if onedrive_desktop.exists() else standard_desktop
project = pathlib.Path(__file__).resolve().parent
vbs = str(project / "launch_dashboard.vbs")
ico = str(project / "branding" / "p2t_icon.ico")

ps_script = desktop / "_mkshortcut.ps1"
lnk_path = str(desktop / "P2T Automation.lnk")

ps_script.write_text(
    f'$ws = New-Object -ComObject WScript.Shell\n'
    f'$s = $ws.CreateShortcut("{lnk_path}")\n'
    f'$s.TargetPath = "wscript.exe"\n'
    f'$s.Arguments = """{vbs}"""\n'
    f'$s.WorkingDirectory = "{project}"\n'
    f'$s.IconLocation = "{ico}"\n'
    f'$s.Description = "P2T Post-Refresh Automation Dashboard"\n'
    f'$s.Save()\n'
)

os.system(f'powershell -ExecutionPolicy Bypass -File "{ps_script}"')
ps_script.unlink()
print("Shortcut created on Desktop!")