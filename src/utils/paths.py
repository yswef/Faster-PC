import sys
import os


def is_frozen() -> bool:
    """True لو التطبيق يشتغل كملف exe مغلّف بـ PyInstaller."""
    return getattr(sys, "frozen", False)


def resource_path(relative_path: str) -> str:
    """
    مسار لموارد للقراءة فقط تُشحن مع التطبيق (docs.html، الأيقونة،
    styles.qss). عند التغليف بـ PyInstaller (--onefile) هذي الملفات
    تُستخرج مؤقتًا لمجلد sys._MEIPASS عند التشغيل، فنبحث هناك أولاً.
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        # جذر المشروع = مجلدين للأعلى من src/utils/paths.py
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative_path)


def app_dir() -> str:
    """
    مجلد التطبيق الفعلي على القرص: مجلد ملف الـ exe نفسه (مو مجلد
    الاستخراج المؤقت لـ PyInstaller). هذا هو المكان الصحيح لأي ملف
    لازم يبقى بعد إغلاق البرنامج (config.json، السجلات).
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def writable_path(relative_path: str) -> str:
    """مسار لملف/مجلد يُقرأ ويُكتب أثناء التشغيل (بجانب الـ exe نفسه، مو داخل حزمة القراءة فقط)."""
    return os.path.join(app_dir(), relative_path)
