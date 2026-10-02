"""
نافذة تسجيل الدخول.

- تظهر بعد إكمال الإعداد الأولي (المعالج ينشئ الحساب).
- حماية من التخمين: 5 محاولات خاطئة → قفل مؤقت متزايد.
- تتذكر آخر مستخدم مسجّل لتسهيل الدخول.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.gui.theme import COLORS
from src.utils.auth import AuthError, AuthManager
from src.version import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
LOCK_SECONDS = 30


class LoginWindow(QDialog):
    """تسجيل الدخول لحساب محلي موجود."""

    def __init__(self, settings_manager):
        super().__init__()
        self.settings = settings_manager
        self.auth = AuthManager(settings_manager)
        self.authenticated_user: dict | None = None
        self._attempts = 0
        self._locked = False

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — تسجيل الدخول")
        self.setMinimumWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel(f"<h2 style='margin:0'>{APP_NAME}</h2>")
        layout.addWidget(header)
        layout.addWidget(QLabel("أدخل بيانات حسابك للمتابعة:"))

        form = QFormLayout()
        self.username_input = QLineEdit()
        self.username_input.setText(str(self.settings.get("last_user") or ""))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form.addRow("اسم المستخدم:", self.username_input)
        form.addRow("كلمة المرور:", self.password_input)
        layout.addLayout(form)

        self.remember_cb = QCheckBox("تذكر اسم المستخدم")
        self.remember_cb.setChecked(True)
        layout.addWidget(self.remember_cb)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"color: {COLORS['danger']};")
        layout.addWidget(self.error_label)

        self.submit_btn = QPushButton("دخول")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.handle_submit)
        layout.addWidget(self.submit_btn)

        self.password_input.returnPressed.connect(self.handle_submit)
        self.username_input.returnPressed.connect(self.handle_submit)
        self.password_input.setFocus()

    # ------------------------------------------------------------------
    def handle_submit(self) -> None:
        if self._locked:
            return
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText("أدخل اسم المستخدم وكلمة المرور.")
            return

        try:
            user = self.auth.authenticate(username, password)
        except Exception as exc:  # pragma: no cover
            logger.exception("Authentication error")
            self.error_label.setText(f"تعذر التحقق من الحساب: {exc}")
            return

        if user is None:
            self._attempts += 1
            remaining = MAX_ATTEMPTS - self._attempts
            if remaining <= 0:
                self._lock()
            else:
                self.error_label.setText(
                    f"اسم المستخدم أو كلمة المرور غير صحيحة. المحاولات المتبقية: {remaining}."
                )
            return

        self.authenticated_user = user
        if self.remember_cb.isChecked():
            self.settings.set("last_user", user["username"])
        logger.info("User logged in: %s", user["username"])
        self.accept()

    def _lock(self) -> None:
        self._locked = True
        self.submit_btn.setEnabled(False)
        self.password_input.setEnabled(False)
        remaining = LOCK_SECONDS

        def _tick():
            nonlocal remaining
            remaining -= 1
            if remaining <= 0:
                self._locked = False
                self._attempts = 0
                self.submit_btn.setEnabled(True)
                self.password_input.setEnabled(True)
                self.error_label.setText("")
                return
            self.error_label.setText(f"محاولات كثيرة خاطئة. أعد المحاولة بعد {remaining} ثانية.")

        timer = QTimer(self)
        timer.timeout.connect(_tick)
        timer.start(1000)
        self.error_label.setText(f"محاولات كثيرة خاطئة. أعد المحاولة بعد {remaining} ثانية.")
        logger.warning("Login temporarily locked after %s failed attempts.", MAX_ATTEMPTS)


def first_run_wizard_required(settings) -> bool:
    """هل يحتاج البرنامج معالج إعداد أولي؟"""
    return not bool(settings.get("setup_completed")) or not (settings.get("users") or [])


__all__ = ["LoginWindow", "first_run_wizard_required", "AuthError"]
