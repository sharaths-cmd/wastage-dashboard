' Double-click this file to start the dashboard silently in the background.
' No CMD window opens, and the server keeps running even after you close everything.
' To stop it later: open Task Manager -> find "pythonw.exe" -> End Task.

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pythonw main.py", 0, False
