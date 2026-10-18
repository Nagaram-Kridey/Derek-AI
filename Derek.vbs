Option Explicit
Dim files, shell, project, python, entry
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
project = files.GetParentFolderName(WScript.ScriptFullName)
python = files.BuildPath(project, ".venv\Scripts\pythonw.exe")
entry = files.BuildPath(project, "desktop\launch.pyw")
If Not files.FileExists(python) Then
  MsgBox "Prepare the project Python environment first. See LOCAL_APP.md.", vbInformation, "Derek setup"
  WScript.Quit 1
End If
shell.CurrentDirectory = project
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & entry & Chr(34), 0, False
