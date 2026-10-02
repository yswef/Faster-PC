"""
التسجيل (Logging) — سجل ملفات دوّار + سجل واجهة آمن من الخيوط + التقاط
الأعطال غير المتوقعة (crash log).

كل رسالة تُسجَّل في مكانين:
- واجهة البرنامج (تبويب السجل) عبر Signal — آمن من أي خيط.
- ملف logs/faster_pc.log (دوار 2MB × 4 نسخ).
وأي استثناء غير ملتقط يُكتب في logs/crash.log مع إشعار للمستخدم بدل انهيار صامت.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QObject, Signal

from src.utils.paths import ensure_dirs, logs_dir

LOG_COLORS = {
    "DEBUG": "#8b8f9e",
    "INFO": "#dcdce3",
    "SUCCESS": "#3fbf7f",
    "WARNING": "#f0ad4e",
    "ERROR": "#e74c3c",
    "CRITICAL": "#ff5c5c",
}

SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def log_success(self: logging.Logger, message, *args, **kwargs):
    """مستوى إضافي للسجل: رسالة نجاح واضحة بصريًا."""
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)


logging.Logger.success = log_success  # type: ignore[attr-defined]

_FILE_HANDLER_NAME = "fasterpc-file"
_MAX_LOG_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 4


class _LogSignalEmitter(QObject):
    """وسيط آمن: أي استدعاء logging من أي خيط ينتقل لخيط الواجهة عبر Signal."""

    log_received = Signal(str, str)  # (formatted_message, level_name)


class UILogHandler(logging.Handler):
    """يعرض سجلات البرنامج داخل تبويب السجل في الواجهة (آمن من الخيوط)."""

    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self._emitter = _LogSignalEmitter()
        # الاتصال تلقائيًا من نوع Queued لأن المُطلِق غالبًا في خيط آخر.
        self._emitter.log_received.connect(self._append_to_ui)

    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        try:
            self._emitter.log_received.emit(msg, record.levelname)
        except RuntimeError:
            # الواجهة أُغلقت أثناء إغلاق البرنامج — لا داعي لعرض شيء.
            pass

    def _append_to_ui(self, msg: str, level_name: str):
        color = LOG_COLORS.get(level_name, "#dcdce3")
        safe_msg = (
            msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ).replace("\n", "<br>")
        try:
            self.text_edit.append(f'<span style="color:{color}">{safe_msg}</span>')
        except RuntimeError:
            pass


def _build_formatter() -> logging.Formatter:
    return logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def setup_file_logging(log_directory: str | None = None, filename: str = "faster_pc.log") -> bool:
    """تفعيل السجل الملفي الدوّار. آمن للاستدعاء أكثر من مرة (لا يكرر المعالجات)."""
    root = logging.getLogger()
    if any(getattr(h, "name", "") == _FILE_HANDLER_NAME for h in root.handlers):
        return True

    directory = log_directory or logs_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(directory, filename),
            maxBytes=_MAX_LOG_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.name = _FILE_HANDLER_NAME
        handler.setFormatter(_build_formatter())
        handler.setLevel(logging.DEBUG)
        root.addHandler(handler)
        return True
    except OSError as exc:
        logging.getLogger(__name__).warning("Could not set up file logging: %s", exc)
        return False


def setup_logging(level: int = logging.INFO) -> None:
    """التهيئة الأساسية: مستوى عام + سجل ملفي + سجل أخطاء منفصل."""
    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        console = logging.StreamHandler()
        console.setFormatter(_build_formatter())
        root.addHandler(console)
    setup_file_logging()
    _setup_error_log()


def _setup_error_log() -> None:
    root = logging.getLogger()
    if any(getattr(h, "name", "") == "fasterpc-errors" for h in root.handlers):
        return
    try:
        handler = RotatingFileHandler(
            os.path.join(logs_dir(), "errors.log"),
            maxBytes=1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        handler.name = "fasterpc-errors"
        handler.setLevel(logging.WARNING)
        handler.setFormatter(_build_formatter())
        root.addHandler(handler)
    except OSError as exc:  # pragma: no cover
        logging.getLogger(__name__).debug("Could not set up error log: %s", exc)


def write_crash_log(exc_type, exc_value, exc_tb) -> str:
    """كتابة استثناء غير ملتقط في logs/crash.log وترجيع المسار."""
    path = os.path.join(logs_dir(), "crash.log")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n" + "=" * 70 + "\n")
            fh.write(f"Date: {datetime.now().isoformat()}\n")
            fh.write(f"Version: {_app_version()}\n")
            fh.write(f"Thread: {threading.current_thread().name}\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        return path
    except OSError:
        return ""


def _app_version() -> str:
    try:
        from src.version import APP_VERSION

        return APP_VERSION
    except Exception:
        return "?"


def install_excepthook(on_error=None) -> None:
    """
    اعتراض أي استثناء غير ملتقط في الخيط الرئيسي أو خيوط العمل:
    يُسجَّل في الملفات، ويُبلَّغ المستخدم برسالة واضحة بدل إغلاق صامت.
    """
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("fasterpc").critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )
        path = write_crash_log(exc_type, exc_value, exc_tb)
        if on_error is not None:
            try:
                on_error(exc_type, exc_value, exc_tb, path)
            except Exception:
                pass

    sys.excepthook = _hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            if args.exc_type is SystemExit:
                return
            logging.getLogger("fasterpc").critical(
                "Unhandled exception in thread %s", args.thread.name if args.thread else "?",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            write_crash_log(args.exc_type, args.exc_value, args.exc_traceback)

        threading.excepthook = _thread_hook  # type: ignore[assignment]


def read_log_tail(lines: int = 200, filename: str = "faster_pc.log") -> str:
    """قراءة آخر أسطر ملف السجل (لتقرير التشخيص)."""
    path = os.path.join(logs_dir(), filename)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.readlines()
        return "".join(content[-lines:])
    except OSError:
        return ""


__all__ = [
    "LOG_COLORS",
    "SUCCESS_LEVEL",
    "UILogHandler",
    "setup_logging",
    "setup_file_logging",
    "install_excepthook",
    "write_crash_log",
    "read_log_tail",
]
