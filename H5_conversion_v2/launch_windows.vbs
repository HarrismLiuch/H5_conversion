' VBScript launcher for the H5 Conversion GUI on Windows.
'
' Double-clicking a .vbs file always runs through Windows Script Host
' (WSH), which can spawn a cmd.exe process that runs a .bat file with
' its own console properties. This is the most reliable way to keep
' the window visible on managed Windows boxes where double-clicking
' a .bat file directly would cause the window to flash closed.
'
' To install: make sure this file is in the same folder as
' launcher_inner.bat, then double-click launch_windows.vbs.

Option Explicit

Dim shell
Dim fso
Dim scriptDir
Dim innerBat
Dim cmdLine

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
innerBat = fso.BuildPath(scriptDir, "launcher_inner.bat")

If Not fso.FileExists(innerBat) Then
    MsgBox "Could not find launcher_inner.bat in:" & vbCrLf & scriptDir, _
           vbCritical, "H5 Conversion"
    WScript.Quit 1
End If

' /k keeps the console open after the script ends, so the user can
' read the result. WindowStyle 1 = SW_SHOWNORMAL.
cmdLine = "cmd.exe /k """ & innerBat & """"
shell.Run cmdLine, 1, False
