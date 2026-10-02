"""
نقطة تشغيل التطبيق:
- تهيئة البيئة (الأيقونة، DPI، هوية التطبيق لويندوز).
- تشغيل نسخة واحدة فقط (منع فتح البرنامج مرتين).
- معالج الإعداد الأولي ثم تسجيل الدخول ثم النافذة الرئيسية.
- التقاط أي خطأ فادح وعرضه برسالة واضحة بدل انهيار صامت.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from src.core.app_context import AppContext
from src.gui.login_window import LoginWindow, first_run_wizard_required
from src.gui.main_window import MainWindow, load_app_icon
from src.gui.setup_wizard import run_setup_if_needed
from src.gui.theme import dark_palette
from src.utils.logger import install_excepthook, setup_logging
from src.utils.paths import ensure_dirs, migrate_legacy_files
from src.utils.winapi import (
    MB_ICONERROR,
    MB_OK,
    enable_dpi_awareness,
    message_box,
    set_app_user_model_id,
)
from src.version import APP_ID, APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)

_SINGLE_INSTANCE_KEY = f"{APP_ID}_single_instance"


class SingleInstance:
    """
    يضمن تشغيل نسخة واحدة من البرنامج لكل مستخدم:
    النسخة الثانية تُرسل "show" للنسخة الأولى وتخرج مباشرة.
    """

    def __init__(self, key: str = _SINGLE_INSTANCE_KEY):
        self.key = key
        self.server: QLocalServer | None = None
        self.is_primary = False

    def try_acquire(self, on_message=None) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.key)
        if socket.waitForConnected(300):
            socket.write(b"show")
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            self.is_primary = False
            return False

        # تنظيف مقبس قديم متروك من انهيار سابق
        QLocalServer.removeServer(self.key)
        self.server = QLocalServer()
        self.server.newConnection.connect(lambda: self._on_connection(on_message))
        if not self.server.listen(self.key):
            logger.warning("Single-instance server could not start: %s", self.server.errorString())
            self.is_primary = True  # لا نمنع التشغيل بسبب فشل هذه الميزة
            return True
        self.is_primary = True
        return True

    def _on_connection(self, on_message) -> None:
        while self.server is not None and self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            try:
                connection.readyRead.connect(lambda: self._read(connection, on_message))
                if connection.bytesAvailable():
                    self._read(connection, on_message)
            except Exception:  # pragma: no cover
                pass

    @staticmethod
    def _read(connection, on_message) -> None:
        try:
            connection.readAll()
        finally:
            connection.disconnectFromServer()
        if on_message is not None:
            on_message()


def _configure_application(app: QApplication, language: str) -> None:
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(load_app_icon())
    app.setPalette(dark_palette())
    if language == "ar":
        app.setLayoutDirection(Qt.RightToLeft)


def _fatal_error_handler(exc_type, exc_value, exc_tb, crash_path: str) -> None:
    """عرض خطأ فادح للمستخدم بطريقة مفهومة (بدل traceback أو إغلاق صامت)."""
    lines = [
        "حدث خطأ غير متوقع وأُغلق البرنامج بشكل آمن.",
        "",
        f"التفاصيل: {exc_value}",
    ]
    if crash_path:
        lines.append(f"سُجّلت التفاصيل في: {crash_path}")
    text = "\n".join(lines)
    try:
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, f"{APP_NAME} — خطأ", text)
        else:
            message_box(f"{APP_NAME} — خطأ", text, MB_OK | MB_ICONERROR)
    except Exception:
        print(text, file=sys.stderr)


def launch_app(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    # 1) تهيئة البيئة قبل أي نافذة
    enable_dpi_awareness()
    set_app_user_model_id(APP_ID)
    ensure_dirs()
    migrate_legacy_files()
    setup_logging()

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)  # نبقى في شريط المهام عند إغلاق النافذة

    # 2) نسخة واحدة فقط
    single = SingleInstance()
    holder: dict = {}

    def _activate_existing() -> None:
        window = holder.get("window")
        if window is not None:
            window.show_normal()

    if not single.try_acquire(on_message=_activate_existing):
        logger.info("Another instance is already running; activating it.")
        return 0

    install_excepthook(on_error=_fatal_error_handler)

    start_minimized = "--minimized" in argv
    exit_code = 0
    try:
        ctx = AppContext()
        _configure_application(app, str((ctx.settings.get("appearance") or {}).get("language", "ar")))

        # 3) الإعداد الأولي عند أول تشغيل
        if first_run_wizard_required(ctx.settings):
            if not run_setup_if_needed(ctx.settings, ctx.installer, ctx.protection):
                logger.info("Setup cancelled by user; exiting.")
                return 0

        # 4) تسجيل الدخول + النافذة الرئيسية (مع دعم تسجيل الخروج وإعادة الدخول)
        while True:
            login = LoginWindow(ctx.settings)
            if login.exec() != LoginWindow.Accepted or login.authenticated_user is None:
                logger.info("Login cancelled; exiting.")
                return exit_code

            ctx.current_user = login.authenticated_user
            window = MainWindow(ctx, login.authenticated_user, start_minimized=start_minimized)
            holder["window"] = window
            window.show()
            start_minimized = False
            app.exec()

            if not window.logged_out:
                break
            holder["window"] = None
        return exit_code
    except Exception as exc:  # pragma: no cover
        logger.exception("Fatal error during startup")
        _fatal_error_handler(type(exc), exc, exc.__traceback__, "")
        return 1
    finally:
        try:
            if single.server is not None:
                single.server.close()
        except Exception:
            pass


def run_headless_check() -> int:
    """
    فحص سريع بدون واجهة (يُستخدم في الاختبارات وفي التحقق بعد التثبيت):
    يتحقق من أن كل الموديولات تُستورد وتُبنى الخدمات الأساسية بنجاح.
    """
    setup_logging()
    ctx = AppContext()
    info = {
        "version": APP_VERSION,
        "config": ctx.settings.config_path,
        "journal": ctx.journal.path,
    }
    print("OK", info)
    return 0


__all__ = ["launch_app", "run_headless_check", "SingleInstance"]
