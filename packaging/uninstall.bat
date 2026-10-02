@echo off
rem ============================================================
rem  Faster PC — إلغاء التثبيت
rem  يحذف: البرنامج + الاختصارات + تسجيل التشغيل التلقائي.
rem  يبقي: ملفات الإعدادات والسجلات (يمكن حذفها يدويًا من
rem        %LOCALAPPDATA%\FasterPC إن رغبت).
rem ============================================================
setlocal EnableExtensions
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
endlocal
