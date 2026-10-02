# -*- mode: python ; coding: utf-8 -*-
"""
ملف بناء PyInstaller — Faster PC
=================================
- console=False: البرنامج يعمل بدون أي نافذة أوامر (تشغيل صامت تمامًا).
- uac_admin=True: يطلب صلاحيات المدير تلقائيًا عند التشغيل (أغلب الميزات تحتاجها).
- icon: أيقونة البرنامج الرسمية تظهر في الملف والاختصار وشريط المهام.
- datas: كل الموارد التي تُقرأ وقت التشغيل (الأنماط، التوثيق، الأيقونات، الترخيص).

البناء:
    pyinstaller --noconfirm --clean faster_pc.spec
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
# ضمان أن حزمة src قابلة للاستيراد وقت البناء (لجمع ملفات البيانات)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from PyInstaller.utils.hooks import collect_data_files
except Exception:  # pragma: no cover
    collect_data_files = None

datas = [
    (str(ROOT / "assets" / "app_icon.ico"), "assets"),
    (str(ROOT / "assets" / "icon_256.png"), "assets"),
    (str(ROOT / "assets" / "icon_512.png"), "assets"),
    (str(ROOT / "src" / "gui" / "styles.qss"), "src/gui"),
    (str(ROOT / "docs" / "docs.html"), "docs"),
    (str(ROOT / "LICENSE"), "."),
]
# أي ملفات .qss إضافية داخل الحزمة (احتياط مستقبلي) — لا نُفشل البناء لو فشل الجمع
if collect_data_files is not None:
    try:
        datas += collect_data_files("src", includes=["**/*.qss"])
    except Exception as exc:  # pragma: no cover
        print(f"[spec] collect_data_files skipped: {exc}")

hiddenimports = [
    "PySide6.QtNetwork",
    "src.utils.winreg_stub",
]

excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtSensors", "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech", "PySide6.QtUiTools", "PySide6.QtVirtualKeyboard",
    "matplotlib", "numpy", "pandas", "tkinter",
]

icon_path = str(ROOT / "assets" / "app_icon.ico")
version_file = str(ROOT / "packaging" / "version_info.txt")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FasterPC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # لا نافذة أوامر إطلاقًا
    disable_windowed_traceback=False,
    icon=icon_path,
    version=version_file,
    uac_admin=True,         # طلب صلاحيات المدير تلقائيًا
    uac_uiaccess=False,
)
