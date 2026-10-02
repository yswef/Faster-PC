"""
مسارات الملفات في التطبيق.

فلسفة المسارات هنا:
- موارد القراءة فقط (styles.qss، docs.html، الأيقونة) تُقرأ من حزمة PyInstaller
  المؤقتة عند التغليف، أو من جذر المشروع أثناء التطوير  -> resource_path()
- الملفات القابلة للكتابة (config.json، السجلات، سجل التغييرات) تُكتب في مجلد
  بيانات المستخدم %LOCALAPPDATA%\\FasterPC عند التشغيل كملف مبني، لأن المجلد
  الذي يُثبَّت فيه البرنامج (Program Files) غالبًا للقراءة فقط.

وضع محمول (Portable): أنشئ ملفًا فارغًا اسمه portable.flag بجانب الملف التنفيذي
فتُكتب كل البيانات بجانبه بدل LOCALAPPDATA.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys

from src.version import APP_ID

logger = logging.getLogger(__name__)

PORTABLE_FLAG = "portable.flag"
_LEGACY_FILES = ("config.json", "faster_pc.log")


# ---------------------------------------------------------------------------
# بيئة التشغيل
# ---------------------------------------------------------------------------
def is_windows() -> bool:
    """True إذا كنا نعمل على ويندوز."""
    return os.name == "nt"


def is_frozen() -> bool:
    """True إذا كان التطبيق يعمل كملف exe مغلّف بـ PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def project_root() -> str:
    """جذر المشروع أثناء التطوير (مجلد يحتوي main.py)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def executable_dir() -> str:
    """المجلد الذي يوجد فيه الملف التنفيذي (أو جذر المشروع في وضع التطوير)."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return project_root()


# ---------------------------------------------------------------------------
# موارد القراءة فقط
# ---------------------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    """
    مسار مورد للقراءة فقط مشحون مع التطبيق (docs.html، styles.qss، الأيقونة).

    عند التغليف بـ PyInstaller يستخرجها البرنامج إلى مجلد مؤقت
    (sys._MEIPASS)، فنقرأ من هناك أولًا، ثم نجرب بجانب الملف التنفيذي كحالة
    ثانية (توزيع محمول بدون بيانات مشحونة).
    """
    candidates = []
    if is_frozen():
        base = getattr(sys, "_MEIPASS", None)
        if base:
            candidates.append(os.path.join(base, relative_path))
        candidates.append(os.path.join(executable_dir(), relative_path))
    else:
        candidates.append(os.path.join(project_root(), relative_path))

    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0] if candidates else relative_path


# ---------------------------------------------------------------------------
# مجلد البيانات القابل للكتابة
# ---------------------------------------------------------------------------
def is_portable() -> bool:
    """True إذا كان المستخدم طلب الوضع المحمول (ملف portable.flag بجانب البرنامج)."""
    return os.path.exists(os.path.join(executable_dir(), PORTABLE_FLAG))


def app_data_dir() -> str:
    """
    مجلد بيانات التطبيق القابل للكتابة:
    - وضع محمول: بجانب الملف التنفيذي.
    - نسخة مبنية: %LOCALAPPDATA%\\FasterPC (مع بديل APPDATA ثم مجلد البرنامج).
    - وضع التطوير: جذر المشروع (حتى تبقى الملفات أمام المطوّر بسهولة).
    """
    if is_portable():
        return executable_dir()

    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return os.path.join(base, APP_ID)
        return executable_dir()

    return project_root()


def writable_path(relative_path: str) -> str:
    """مسار ملف/مجلد يُقرأ ويُكتب أثناء التشغيل."""
    return os.path.join(app_data_dir(), relative_path)


def config_path() -> str:
    """مسار ملف الإعدادات config.json."""
    return writable_path("config.json")


def journal_path() -> str:
    """مسار سجل التغييرات القابلة للتراجع changes.json."""
    return writable_path("changes.json")


def logs_dir() -> str:
    """مجلد السجلات."""
    return writable_path("logs")


def shortcuts_dir() -> str:
    """مجلد اختصارات التطبيق على سطح المكتب/قائمة ابدأ."""
    return writable_path("shortcuts")


def ensure_dirs() -> None:
    """إنشاء مجلدات البيانات المطلوبة (آمنة الاستدعاء أكثر من مرة)."""
    for path in (app_data_dir(), logs_dir()):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:  # pragma: no cover - يعتمد على صلاحيات النظام
            logger.warning("Could not create directory %s: %s", path, exc)


def migrate_legacy_files() -> list[str]:
    """
    ترحيل الملفات من التوزيع القديم (كانت تُكتب بجانب الملف التنفيذي دائمًا)
    إلى مجلد بيانات المستخدم الجديد. تُنفَّذ مرة واحدة فقط: إن كان الملف
    القديم موجودًا والجديد غير موجود، يُنسخ القديم بدل ما يضيع.
    ترجع قائمة الملفات التي رُحّلت.
    """
    migrated: list[str] = []
    target_dir = app_data_dir()
    source_dir = executable_dir()

    if os.path.abspath(target_dir) == os.path.abspath(source_dir):
        return migrated

    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError:
        return migrated

    for name in _LEGACY_FILES:
        old = os.path.join(source_dir, name)
        new = os.path.join(target_dir, name)
        if os.path.exists(old) and not os.path.exists(new):
            try:
                shutil.copy2(old, new)
                migrated.append(name)
            except OSError as exc:  # pragma: no cover
                logger.debug("Legacy migration failed for %s: %s", name, exc)

    # مجلد السجلات القديم
    old_logs = os.path.join(source_dir, "logs")
    new_logs = logs_dir()
    if os.path.isdir(old_logs) and not os.path.isdir(new_logs):
        try:
            shutil.copytree(old_logs, new_logs)
            migrated.append("logs/")
        except OSError:  # pragma: no cover
            pass

    if migrated:
        logger.info("Migrated legacy files to %s: %s", target_dir, ", ".join(migrated))
    return migrated


def human_size(num_bytes: float) -> str:
    """تحويل حجم بالبايت إلى نص مقروء (KB/MB/GB)."""
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


__all__ = [
    "PORTABLE_FLAG",
    "is_windows",
    "is_frozen",
    "is_portable",
    "project_root",
    "executable_dir",
    "resource_path",
    "app_data_dir",
    "writable_path",
    "config_path",
    "journal_path",
    "logs_dir",
    "shortcuts_dir",
    "ensure_dirs",
    "migrate_legacy_files",
    "human_size",
]
