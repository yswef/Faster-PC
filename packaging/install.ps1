# ============================================================
#  Faster PC — سكربت التثبيت الصامت (يُستدعى من install.bat)
#  ينفّذ: نسخ الملفات + اختصار سطح المكتب + قائمة ابدأ +
#         تسجيل التشغيل التلقائي (اختياري) + تشغيل الإعداد.
#  كل النوافذ مخفية: لا يظهر أي cmd أو PowerShell للمستخدم.
# ============================================================
param(
    [string]$SourceDir = $PSScriptRoot,
    [switch]$NoDesktopShortcut,
    [switch]$NoStartMenuShortcut,
    [switch]$RunAtStartup,
    [switch]$NoLaunch,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

$appName    = 'Faster PC'
$exeName    = 'FasterPC.exe'
$sourceExe  = Join-Path $SourceDir $exeName

if (-not (Test-Path $sourceExe)) {
    Write-Error "لم يُعثر على $exeName في $SourceDir"
    exit 1
}

# مجلد التثبيت داخل حساب المستخدم (لا يحتاج صلاحيات مدير للنسخ)
$installDir = Join-Path $env:LOCALAPPDATA "Programs\$appName"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

if (-not $Quiet) { Write-Host "نسخ الملفات إلى: $installDir" }
Copy-Item -Path $sourceExe -Destination (Join-Path $installDir $exeName) -Force

# نسخ أي ملفات مرافقة مفيدة
foreach ($extra in @('LICENSE', 'uninstall.bat')) {
    $p = Join-Path $SourceDir $extra
    if (Test-Path $p) { Copy-Item $p -Destination $installDir -Force }
}

$targetExe = Join-Path $installDir $exeName
$iconPath  = $targetExe  # الأيقونة مدمجة في الملف التنفيذي

function New-AppShortcut {
    param([string]$ShortcutPath, [string]$Target, [string]$Arguments = '', [string]$WorkDir = '')
    $dir = Split-Path -Parent $ShortcutPath
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = if ($WorkDir) { $WorkDir } else { Split-Path -Parent $Target }
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.Description = 'Faster PC — صيانة وتسريع ويندوز'
    $shortcut.Save()
}

if (-not $NoDesktopShortcut) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    New-AppShortcut -ShortcutPath (Join-Path $desktop "$appName.lnk") -Target $targetExe
    if (-not $Quiet) { Write-Host "✔ اختصار سطح المكتب" }
}

if (-not $NoStartMenuShortcut) {
    $programs = Join-Path ([Environment]::GetFolderPath('Programs')) $appName
    New-AppShortcut -ShortcutPath (Join-Path $programs "$appName.lnk") -Target $targetExe
    if (-not $Quiet) { Write-Host "✔ اختصار قائمة ابدأ" }
}

if ($RunAtStartup) {
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    Set-ItemProperty -Path $runKey -Name $appName -Value "`"$targetExe`" --minimized"
    if (-not $Quiet) { Write-Host "✔ التشغيل التلقائي مع ويندوز" }
}

# اختصار إلغاء التثبيت
$uninstaller = Join-Path $installDir 'uninstall.bat'
if (-not (Test-Path $uninstaller)) {
    @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
"@ | Set-Content -Path $uninstaller -Encoding OEM
}

if (-not $NoLaunch) {
    if (-not $Quiet) { Write-Host "تشغيل البرنامج لأول مرة لإكمال الإعداد..." }
    Start-Process -FilePath $targetExe
}

if (-not $Quiet) {
    Write-Host ''
    Write-Host 'تم تثبيت Faster PC بنجاح.'
    Write-Host "مجلد التثبيت: $installDir"
}
exit 0
