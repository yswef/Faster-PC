# ============================================================
#  Faster PC — إلغاء التثبيت (صامت)
#  يحذف البرنامج والاختصارات وتسجيل التشغيل التلقائي، ويُبقي
#  ملفات الإعدادات والسجلات في %LOCALAPPDATA%\FasterPC.
# ============================================================
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Faster PC'),
    [switch]$RemoveUserData,
    [switch]$Quiet
)

$ErrorActionPreference = 'SilentlyContinue'
$appName = 'Faster PC'

# 1) إغلاق البرنامج إن كان يعمل
Get-Process -Name 'FasterPC' | Stop-Process -Force

# 2) حذف الاختصارات
$desktop = [Environment]::GetFolderPath('Desktop')
Remove-Item -Path (Join-Path $desktop "$appName.lnk") -Force

$programs = [Environment]::GetFolderPath('Programs')
Remove-Item -Path (Join-Path $programs $appName) -Recurse -Force

# 3) إزالة تسجيل التشغيل التلقائي
Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name $appName

# 4) حذف مجلد التثبيت
Remove-Item -Path $InstallDir -Recurse -Force

# 5) بيانات المستخدم (اختياري)
if ($RemoveUserData) {
    Remove-Item -Path (Join-Path $env:LOCALAPPDATA 'FasterPC') -Recurse -Force
}

if (-not $Quiet) {
    Write-Host 'تم إلغاء تثبيت Faster PC.'
    Write-Host "بيانات الإعدادات بقيت في: $env:LOCALAPPDATA\FasterPC"
}
exit 0
