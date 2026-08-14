Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run Chr(34) & sh.CurrentDirectory & "\.venv\Scripts\pythonw.exe" & Chr(34) & " " & Chr(34) & sh.CurrentDirectory & "\outbound_worker.py" & Chr(34), 0, False
