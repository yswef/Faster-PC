' ============================================================
'  Faster PC — تثبيت صامت تمامًا (بدون أي نافذة على الإطلاق)
'  دبل-كلك على هذا الملف فقط. ينفّذ install.ps1 في الخلفية.
' ============================================================
Option Explicit
Dim shell, fso, baseDir, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & baseDir & "\install.ps1"" -SourceDir """ & baseDir & """"
' 0 = نافذة مخفية، False = لا ننتظر انتهاءها (التثبيت يكمل في الخلفية)
shell.Run cmd, 0, False
