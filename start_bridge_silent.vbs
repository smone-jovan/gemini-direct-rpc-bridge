Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir
WshShell.Run "cmd.exe /c """"" & "C:\Users\ROG\AppData\Local\Programs\Python\Python313\python.exe" & """ bridge.py > out.log 2> err.log""", 0, False
