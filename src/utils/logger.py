import logging
import os
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal

from src.utils.paths import writable_path

LOG_COLORS = {
    "DEBUG": "#888888",
    "INFO": "#dddddd",
    "WARNING": "#f0ad4e",
    "ERROR": "#e74c3c",
    "CRITICAL": "#ff0000",
}


class _LogSignalEmitter(QObject):
    """
    وسيط بسيط لإرسال سجلات الـ logging لواجهة Qt.
    مهم: QTextEdit ماله عملية آمنة عند التحديث من خيط (thread) غير خيط الواجهة
    الرئيسي. باستخدام Signal، أي استدعاء logging.info(...) من أي خيط
    (مثلاً أثناء عملية تنظيف أو فحص تعمل بخيط منفصل) ينتقل بأمان لخيط الواجهة
    قبل ما يلمس QTextEdit.
    """

    log_received = Signal(str, str)  # (formatted_message, level_name)


class UILogHandler(logging.Handler):
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self._emitter = _LogSignalEmitter()
        self._emitter.log_received.connect(self._append_to_ui)

    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        # هذا الاستدعاء آمن من أي خيط لأنه بس يُطلق Signal
        self._emitter.log_received.emit(msg, record.levelname)

    def _append_to_ui(self, msg, level_name):
        color = LOG_COLORS.get(level_name, "#dddddd")
        safe_msg = (
            msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        self.text_edit.append(f'<span style="color:{color}">{safe_msg}</span>')


def setup_file_logging(log_dir=None, filename="faster_pc.log"):
    """
    يفعّل سجل ملفات دوّار (rotating) للاحتفاظ بسجل تشخيصي دائم على القرص —
    مفيد لتتبع أي مشكلة صارت بجلسة سابقة، ويساعد بالدعم الفني بدون ما يحتاج
    المستخدم يعيد إنتاج المشكلة.
    """
    log_dir = log_dir or writable_path("logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, filename),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        return True
    except OSError as e:
        logging.getLogger(__name__).warning(f"Could not set up file logging: {e}")
        return False
