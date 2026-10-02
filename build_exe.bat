@echo off
rem ============================================================
rem  Faster PC — بناء ملف تنفيذي واحد (FasterPC.exe)
rem  التشغيل: دبل-كلك على هذا الملف فقط.
rem  النتيجة: dist\FasterPC.exe + dist\install.bat
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/4] التحقق من بايثون...
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [خطأ] بايثون غير مثبت. حمّله من https://www.python.org/downloads/ ثم أعد المحاولة.
    pause
    exit /b 1
)

echo [2/4] تجهيز بيئة البناء...
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv || (echo [خطأ] تعذر إنشاء بيئة البناء. & pause & exit /b 1)
)
set "VENV_PY=.venv\Scripts\python.exe"
"%VENV_PY%" -m pip install --upgrade pip --quiet
"%VENV_PY%" -m pip install -r requirements.txt -r requirements-dev.txt --quiet || (
    echo [خطأ] تعذر تثبيت المتطلبات. تحقق من اتصال الإنترنت.
    pause
    exit /b 1
)

echo [3/4] بناء البرنامج (بدون نوافذ إضافية)...
"%VENV_PY%" -m PyInstaller --noconfirm --clean faster_pc.spec || (
    echo [خطأ] فشل البناء. راجع الرسائل أعلاه.
    pause
    exit /b 1
)

echo [4/4] تجهيز ملفات التثبيت...
copy /y "packaging\install.bat" "dist\install.bat" >nul 2>nul
copy /y "packaging\install.ps1" "dist\install.ps1" >nul 2>nul
copy /y "packaging\uninstall.bat" "dist\uninstall.bat" >nul 2>nul
copy /y "packaging\uninstall.ps1" "dist\uninstall.ps1" >nul 2>nul
copy /y "packaging\install.vbs" "dist\install.vbs" >nul 2>nul
copy /y "packaging\uninstall.vbs" "dist\uninstall.vbs" >nul 2>nul
if exist "LICENSE" copy /y "LICENSE" "dist\LICENSE" >nul 2>nul

echo.
echo ============================================================
echo  تم البناء بنجاح:
echo    dist\FasterPC.exe      (البرنامج — يعمل صامتًا وبدون cmd)
echo    dist\install.bat       (يثبّت البرنامج + اختصار سطح المكتب)
echo    dist\install.vbs       (تثبيت صامت تمامًا بدون أي نافذة)
echo ============================================================
echo.
pause
endlocal
