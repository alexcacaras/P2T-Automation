' P2T Post-Refresh Automation Dashboard Launcher
Dim WshShell, FSOObj, ProjectDir

Set WshShell = CreateObject("WScript.Shell")
Set FSOObj = CreateObject("Scripting.FileSystemObject")

ProjectDir = FSOObj.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ProjectDir

' Kill any existing dashboard process on port 5000
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do taskkill /f /pid %a 2>nul", 0, True

' Wait for old process to die
WScript.Sleep 1000

' Start Flask server silently
WshShell.Run "cmd /c "".venv\Scripts\python.exe"" dashboard_api.py", 0, False

' Wait for Flask to start
WScript.Sleep 2000

' Open browser
WshShell.Run "http://localhost:5000", 1, False

Set FSOObj = Nothing
Set WshShell = Nothing