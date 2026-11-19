Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir
WshShell.Run """C:\Users\ROG\AppData\Local\Programs\Python\Python313\python.exe"" bridge.py", 0, False
