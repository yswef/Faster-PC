"""
طبقة ويندوز الموحّدة: كل استدعاء لويندوز (subprocess، ريجستري، اختصارات،
أذونات) يمر من هنا، لأسباب ثلاثة:

1) الصمت الكامل: أي أمر خارجي (sc / powercfg / DISM / sfc / chkdsk / netsh)
   يُشغَّل بـ CREATE_NO_WINDOW مع STARTUPINFO مخفي — فلا تظهر أي نافذة سوداء
   (cmd) أثناء عمل البرنامج، لا عند التشغيل ولا أثناء العمليات.
2) الأمان: أوامر على شكل قوائم بدون shell=True (لا حقن أوامر)، وقراءة مخرجات
   بترميز صحيح مهما كانت لغة واجهة ويندوز.
3) العمل على غير ويندوز: كل الدوال ترجع قيمة آمنة بدل ما ترمي استثناء، وهذا
   يسمح بتشغيل الاختبارات والفحص الفني على أي نظام.
"""

from __future__ import annotations

import ctypes
import locale
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == "nt"

# ثوابت ويندوز (نعرّفها يدويًا لتعمل حتى لو لم تكن معرفة في بايثون الحالي)
CREATE_NO_WINDOW = 0x08000000
SW_HIDE = 0
MB_ICONERROR = 0x00000010
MB_ICONWARNING = 0x00000030
MB_ICONINFORMATION = 0x00000040
MB_OK = 0x00000000

# معرفات مجلدات ويندوز المعروفة (KNOWNFOLDERID)
_FOLDER_IDS = {
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "programs": "{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}",
    "start_menu": "{625B53C3-AB48-4EC1-BA1F-A1EF4146FC19}",
    "startup": "{B97D20BB-F46A-4C97-BA10-5E3608430854}",
    "local_appdata": "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}",
    "roaming_appdata": "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}",
    "windows": "{F38BF404-1D43-42F2-9305-67DE0B28FC23}",
}


# ---------------------------------------------------------------------------
# تشغيل الأوامر بصمت
# ---------------------------------------------------------------------------
@dataclass
class CommandResult:
    """نتيجة أمر خارجي بصيغة موحّدة."""

    command: object
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        """المخرجات الكاملة (stdout + stderr) للنص/العرض."""
        parts = [p for p in (self.stdout, self.stderr) if p]
        return "\n".join(parts).strip()

    def __bool__(self) -> bool:  # allows `if result:`
        return self.ok


def _decode(raw) -> str:
    """فك ترميز مخرجات أوامر ويندوز بذكاء (قد تكون UTF-8 أو ترميز صفحة النظام)."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    encodings = []
    if os.name == "nt":
        try:
            encodings.append(f"cp{ctypes.windll.kernel32.GetOEMCP()}")
        except Exception:
            pass
        try:
            encodings.append(f"cp{ctypes.windll.kernel32.GetACP()}")
        except Exception:
            pass
    try:
        encodings.append(locale.getpreferredencoding(False))
    except Exception:
        pass
    encodings += ["utf-8", "cp1256", "latin-1"]
    for enc in encodings:
        if not enc:
            continue
        try:
            return raw.decode(enc, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def hidden_process_kwargs() -> dict:
    """
    وسائط تشغيل تجعل أي عملية فرعية مخفية تمامًا على ويندوز:
    CREATE_NO_WINDOW + STARTUPINFO مع SW_HIDE (تغطية كاملة للحالات).
    """
    if not IS_WINDOWS:
        return {}
    kwargs: dict = {"creationflags": CREATE_NO_WINDOW}
    try:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = SW_HIDE
        kwargs["startupinfo"] = startup
    except Exception:  # pragma: no cover
        pass
    return kwargs


def run_silent(cmd, timeout: int = 60, cwd: str | None = None) -> CommandResult:
    """
    تشغيل أمر خارجي بدون أي نافذة ظاهرة وبدون shell.

    cmd: قائمة أوامر (مفضّل) أو نص (سيُقسَّم تلقائيًا على ويندوز).
    """
    if isinstance(cmd, str):
        cmd = _split_command(cmd)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            shell=False,
            **hidden_process_kwargs(),
        )
        return CommandResult(
            command=cmd,
            returncode=proc.returncode,
            stdout=_decode(proc.stdout),
            stderr=_decode(proc.stderr),
        )
    except FileNotFoundError:
        return CommandResult(command=cmd, returncode=-1, error="الأمر غير موجود على هذا النظام.")
    except subprocess.TimeoutExpired:
        return CommandResult(command=cmd, returncode=-1, error="انتهت مهلة العملية.")
    except (OSError, ValueError) as exc:
        return CommandResult(command=cmd, returncode=-1, error=str(exc))


def _split_command(command: str) -> list[str]:
    """
    تقسيم نص أمر إلى قائمة بدون shell. نستخدم posix=False حتى لا تُبتلع
    الشرطات المائلة العكسية في مسارات ويندوز (C:\\Program Files\\...)،
    ثم نزيل علامات الاقتباس المحيطة بكل جزء يدويًا.
    """
    import shlex

    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        parts = command.split()

    cleaned = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in ("'", '"'):
            part = part[1:-1]
        cleaned.append(part)
    return cleaned


def run_powershell(script: str, timeout: int = 120) -> CommandResult:
    """
    تشغيل سكربت PowerShell بصمت تام وبدون سياسات تنفيذ معطّلة:
    -NoProfile -NonInteractive -ExecutionPolicy Bypass.
    """
    exe = shutil.which("powershell") or "powershell"
    return run_silent(
        [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# أذونات المدير
# ---------------------------------------------------------------------------
def is_admin() -> bool:
    """True إذا كان البرنامج يعمل بصلاحيات مدير النظام."""
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(extra_args: list[str] | None = None) -> bool:
    """
    إعادة تشغيل التطبيق بصلاحيات مدير (نافذة UAC).
    ترجع True إذا قُبل الطلب، وتُترك العملية الحالية للمُستدعي ليغلقها.
    """
    if not IS_WINDOWS:
        return False
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = " ".join(extra_args or [])
        else:
            exe = sys.executable
            script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
            params = f'"{script}" ' + " ".join(extra_args or [])
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, os.path.dirname(os.path.abspath(exe)), 1
        )
        return int(result) > 32
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to relaunch as admin: %s", exc)
        return False


def message_box(title: str, text: str, flags: int = MB_OK | MB_ICONINFORMATION) -> int:
    """صندوق رسالة أصلي من ويندوز (يُستخدم عند الأخطاء الفادحة قبل/بعد إغلاق Qt)."""
    if not IS_WINDOWS:
        return 0
    try:
        return int(ctypes.windll.user32.MessageBoxW(None, text, title, flags))
    except Exception:  # pragma: no cover
        return 0


# ---------------------------------------------------------------------------
# معلومات النظام
# ---------------------------------------------------------------------------
def set_app_user_model_id(app_id: str) -> None:
    """
    تعريف هوية التطبيق لويندوز: بدون هذا يظهر أيقونة بايثون/الأيقونة الافتراضية
    في شريط المهام بدل أيقونة البرنامج.
    """
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:  # pragma: no cover
        logger.debug("SetCurrentProcessExplicitAppUserModelID failed", exc_info=True)


def enable_dpi_awareness() -> None:
    """تفعيل الوعي بدقة الشاشة (Per-Monitor V2) لواجهة واضحة على الشاشات عالية الدقة."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # pragma: no cover
        logger.debug("DPI awareness setup failed", exc_info=True)


def windows_drive() -> str:
    """حرف قرص النظام (C:\\ على الأغلب)."""
    if IS_WINDOWS:
        drive = os.environ.get("SystemDrive") or os.environ.get("SystemRoot", "C:\\")[:2]
        return (drive or "C:").rstrip("\\") + "\\"
    return "/"


def windows_dir() -> str:
    """مجلد ويندوز (C:\\Windows)."""
    if IS_WINDOWS:
        return os.environ.get("SystemRoot", r"C:\Windows")
    return "/"


def system32_dir() -> str:
    return os.path.join(windows_dir(), "System32") if IS_WINDOWS else "/usr/lib"


class GUID(ctypes.Structure):
    """بنية GUID لواجهات ويندوز عبر ctypes."""

    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, text: str):
        super().__init__()
        cleaned = text.strip().strip("{}")
        parts = cleaned.split("-")
        if len(parts) != 5:
            raise ValueError(f"Invalid GUID: {text}")
        self.Data1 = int(parts[0], 16)
        self.Data2 = int(parts[1], 16)
        self.Data3 = int(parts[2], 16)
        tail = bytes.fromhex(parts[3] + parts[4])
        for i, byte in enumerate(tail):
            self.Data4[i] = byte


def known_folder(name: str) -> str | None:
    """
    مسار مجلد ويندوز معروف (سطح المكتب، قائمة ابدأ، Startup...) عبر
    SHGetKnownFolderPath — الطريقة الصحيحة لأنها تراعي توجيه المجلدات
    (مثال: سطح مكتب موجّه إلى OneDrive).
    """
    if not name or name not in _FOLDER_IDS:
        return None
    if IS_WINDOWS:
        try:
            ptr = ctypes.c_wchar_p()
            guid = GUID(_FOLDER_IDS[name])
            shell32 = ctypes.windll.shell32
            ole32 = ctypes.windll.ole32
            ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            res = shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(ptr)
            )
            if res == 0 and ptr.value:
                path = ptr.value
                try:
                    ole32.CoTaskMemFree(ctypes.cast(ptr, ctypes.c_void_p))
                except Exception:
                    pass
                return path
        except Exception as exc:  # pragma: no cover
            logger.debug("known_folder(%s) failed: %s", name, exc)

    # بدائل احتياطية عبر متغيرات البيئة
    home = os.path.expanduser("~")
    fallbacks = {
        "desktop": os.path.join(home, "Desktop"),
        "programs": os.path.join(
            os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming")),
            "Microsoft", "Windows", "Start Menu", "Programs",
        ),
        "start_menu": os.path.join(
            os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming")),
            "Microsoft", "Windows", "Start Menu",
        ),
        "startup": os.path.join(
            os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming")),
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
        ),
        "local_appdata": os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local")),
        "roaming_appdata": os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming")),
        "windows": os.environ.get("SystemRoot", r"C:\Windows"),
    }
    return fallbacks.get(name)


def desktop_dir() -> str:
    return known_folder("desktop") or os.path.expanduser("~")


def start_menu_programs_dir() -> str:
    return known_folder("programs") or os.path.expanduser("~")


def startup_dir() -> str:
    return known_folder("startup") or os.path.expanduser("~")


def get_windows_info() -> dict:
    """معلومات نسخة ويندوز الحالية لعرضها في 'حول البرنامج' وتقارير الفحص."""
    info = {
        "name": "نظام غير معروف",
        "version": "",
        "build": "",
        "edition": "",
        "architecture": "64-bit" if sys.maxsize > 2**32 else "32-bit",
    }
    if not IS_WINDOWS:
        info["name"] = f"{os.uname().sysname} {os.uname().release}" if hasattr(os, "uname") else "Linux"
        return info
    try:
        import winreg

        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            def _get(name, default=""):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except OSError:
                    return default

            product = _get("ProductName", "Windows")
            build = str(_get("CurrentBuild", ""))
            ubr = _get("UBR", "")
            info["version"] = _get("DisplayVersion", "") or _get("ReleaseId", "")
            info["build"] = f"{build}.{ubr}" if ubr else build
            info["edition"] = _get("EditionID", "")
            try:
                build_num = int(build)
            except (TypeError, ValueError):
                build_num = 0
            if build_num >= 22000 and "Windows 10" in product:
                product = product.replace("Windows 10", "Windows 11")
            info["name"] = product
    except Exception as exc:  # pragma: no cover
        logger.debug("Could not read Windows version: %s", exc)
    return info


# ---------------------------------------------------------------------------
# الاختصارات (سطح المكتب / قائمة ابدأ / بدء التشغيل)
# ---------------------------------------------------------------------------
def _ps_escape(value: str) -> str:
    """تهريب نص لسكربت PowerShell (تكرار علامة الاقتباس المفردة)."""
    return (value or "").replace("'", "''")


def create_shortcut(
    shortcut_path: str,
    target_path: str,
    arguments: str = "",
    icon_path: str = "",
    workdir: str = "",
    description: str = "",
) -> bool:
    """
    إنشاء اختصار .lnk حقيقي في أي مكان (سطح المكتب، قائمة ابدأ، Startup)
    عبر WScript.Shell بشكل صامت تمامًا.
    """
    if not IS_WINDOWS:
        logger.info("create_shortcut skipped (not Windows): %s", shortcut_path)
        return False

    os.makedirs(os.path.dirname(os.path.abspath(shortcut_path)), exist_ok=True)
    icon = icon_path or target_path
    script = (
        "$ErrorActionPreference='Stop';"
        "$ws = New-Object -ComObject WScript.Shell;"
        f"$sc = $ws.CreateShortcut('{_ps_escape(shortcut_path)}');"
        f"$sc.TargetPath = '{_ps_escape(target_path)}';"
        f"$sc.Arguments = '{_ps_escape(arguments)}';"
        f"$sc.WorkingDirectory = '{_ps_escape(workdir or os.path.dirname(target_path))}';"
        f"$sc.IconLocation = '{_ps_escape(icon)}';"
        f"$sc.Description = '{_ps_escape(description)}';"
        "$sc.Save();"
    )
    result = run_powershell(script, timeout=45)
    if result.ok and os.path.exists(shortcut_path):
        logger.info("Shortcut created: %s", shortcut_path)
        return True
    logger.warning("Could not create shortcut %s: %s", shortcut_path, result.output)
    return False


def remove_shortcut(shortcut_path: str) -> bool:
    """حذف اختصار .lnk إن وُجد."""
    try:
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            logger.info("Shortcut removed: %s", shortcut_path)
        return True
    except OSError as exc:  # pragma: no cover
        logger.warning("Could not remove shortcut %s: %s", shortcut_path, exc)
        return False


def launcher_details() -> tuple[str, str, str]:
    """
    تفاصيل تشغيل التطبيق لاستخدامها في الاختصارات وبدء التشغيل:
    (الملف الهدف، الوسائط، مسار العمل)

    - نسخة مبنية: الملف التنفيذي نفسه.
    - وضع التطوير: pythonw.exe مع مسار main.py (بدون نافذة كونسول).
    """
    from src.utils.paths import executable_dir, project_root

    if getattr(sys, "frozen", False):
        return sys.executable, "", os.path.dirname(os.path.abspath(sys.executable))

    root = project_root()
    main_py = os.path.join(root, "main.py")
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    interpreter = pythonw if os.path.exists(pythonw) else sys.executable
    return interpreter, f'"{main_py}"', executable_dir()


def create_app_shortcut(
    location: str,
    name: str = "Faster PC",
    icon_path: str = "",
    arguments: str = "",
    description: str = "Faster PC — صيانة وتسريع ويندوز",
) -> str | None:
    """
    إنشاء اختصار للتطبيق في مكان معروف: "desktop" أو "start_menu" أو "startup".
    ترجع مسار الاختصار أو None عند الفشل.
    """
    folders = {
        "desktop": desktop_dir,
        "start_menu": lambda: os.path.join(known_folder("programs") or os.path.expanduser("~"), "Faster PC"),
        "startup": startup_dir,
    }
    folder_fn = folders.get(location)
    if folder_fn is None:
        logger.warning("Unknown shortcut location: %s", location)
        return None
    folder = folder_fn()
    target, default_args, workdir = launcher_details()
    shortcut_path = os.path.join(folder, f"{name}.lnk")
    ok = create_shortcut(
        shortcut_path,
        target,
        arguments=arguments or default_args,
        icon_path=icon_path or target,
        workdir=workdir,
        description=description,
    )
    return shortcut_path if ok else None


def set_run_at_startup(app_name: str, enabled: bool, arguments: str = "--minimized") -> bool:
    """
    تشغيل البرنامج تلقائيًا مع ويندوز عبر مفتاح HKCU\\...\\Run
    (لا يحتاج صلاحيات مدير، ويُلغى بنفس السهولة).
    """
    if not IS_WINDOWS:
        return False
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        target, default_args, _ = launcher_details()
        args = arguments or default_args
        command = f'"{target}" {args}'.strip()

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
                logger.info("Startup registration enabled: %s", command)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logger.info("Startup registration removed.")
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:  # pragma: no cover
        logger.error("Could not change startup registration: %s", exc)
        return False


def is_run_at_startup(app_name: str) -> bool:
    """هل التطبيق مسجّل للتشغيل التلقائي مع ويندوز؟"""
    if not IS_WINDOWS:
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
        ) as key:
            winreg.QueryValueEx(key, app_name)
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# سلة المحذوفات
# ---------------------------------------------------------------------------
_SHERB_FLAGS = 0x1 | 0x2 | 0x4  # NOCONFIRMATION | NOPROGRESS | NOSOUND


def empty_recycle_bin() -> bool:
    """
    إفراغ سلة المحذوفات مباشرة عبر Shell API (بدون winshell وبدون أي نافذة
    تأكيد أو شريط تقدم). ترجع True لو نجحت العملية.
    """
    if not IS_WINDOWS:
        return False
    try:
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, _SHERB_FLAGS)
        if res == 0:
            logger.info("Recycle Bin emptied.")
            return True
        logger.warning("SHEmptyRecycleBinW returned %s", res)
        return res in (0x8000FFFF, -2147418113)  # E_UNEXPECTED: السلة فارغة أصلًا
    except Exception as exc:  # pragma: no cover
        logger.error("Could not empty Recycle Bin: %s", exc)
        return False


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_longlong),
        ("i64NumItems", ctypes.c_longlong),
    ]


def recycle_bin_size() -> tuple[int, int]:
    """حجم سلة المحذوفات بالبايت وعدد العناصر: (size, items)."""
    if not IS_WINDOWS:
        return (0, 0)
    try:
        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res == 0:
            return (max(0, int(info.i64Size)), max(0, int(info.i64NumItems)))
    except Exception:  # pragma: no cover
        logger.debug("SHQueryRecycleBinW failed", exc_info=True)
    return (0, 0)


__all__ = [
    "IS_WINDOWS",
    "CREATE_NO_WINDOW",
    "CommandResult",
    "run_silent",
    "run_powershell",
    "hidden_process_kwargs",
    "is_admin",
    "relaunch_as_admin",
    "message_box",
    "set_app_user_model_id",
    "enable_dpi_awareness",
    "windows_drive",
    "windows_dir",
    "system32_dir",
    "known_folder",
    "desktop_dir",
    "start_menu_programs_dir",
    "startup_dir",
    "get_windows_info",
    "create_shortcut",
    "remove_shortcut",
    "launcher_details",
    "create_app_shortcut",
    "set_run_at_startup",
    "is_run_at_startup",
    "empty_recycle_bin",
    "recycle_bin_size",
    "MB_ICONERROR",
    "MB_ICONWARNING",
    "MB_ICONINFORMATION",
    "MB_OK",
]
