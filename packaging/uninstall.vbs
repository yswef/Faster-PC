' ============================================================
'  Faster PC — إلغاء تثبيت صامت تمامًا (بدون أي نافذة)
' ============================================================
Option Explicit
Dim shell, fso, baseDir, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & baseDir & "\uninstall.ps1"" -Quiet"
shell.Run cmd, 0, False
