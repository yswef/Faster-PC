@echo off
rem ============================================================
rem  Faster PC — التثبيت لجهازك
rem  ينسخ البرنامج إلى مجلد المستخدم، وينشئ اختصارات بالصورة
rem  الرسمية (سطح المكتب + قائمة ابدأ)، ويسجّل التشغيل مع ويندوز
rem  (اختياريًا)، ثم يشغّل البرنامج لأول مرة لإكمال الإعداد.
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "FasterPC.exe" (
    echo [خطأ] لم يُعثر على FasterPC.exe بجانب هذا الملف.
    echo        شغّل build_exe.bat أولاً لبناء البرنامج.
    pause
    exit /b 1
)

echo تثبيت Faster PC...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -SourceDir "%~dp0" %*

if errorlevel 1 (
    echo [خطأ] تعذر إكمال التثبيت.
    pause
    exit /b 1
)

endlocal
