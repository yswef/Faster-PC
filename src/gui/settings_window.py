import webbrowser
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFormLayout, QMessageBox, QGroupBox, QComboBox
)

from src.utils.auth import AuthManager, AuthError

logger = logging.getLogger(__name__)


class SettingsWindow(QDialog):
    def __init__(self, settings_manager, current_user=None):
        super().__init__()
        self.settings = settings_manager
        self.current_user = current_user or {}
        self.auth = AuthManager(settings_manager)
        self.setWindowTitle("الإعدادات")
        self.setMinimumSize(440, 520)

        layout = QVBoxLayout()
        form = QFormLayout()

        self.test_mode_cb = QCheckBox("الوضع التجريبي (تسجيل الإجراءات بدون تنفيذها فعليًا)")
        self.test_mode_cb.setChecked(bool(self.settings.get("test_mode")))
        layout.addWidget(self.test_mode_cb)

        self.auto_clean_cb = QCheckBox("تنظيف تلقائي للملفات المؤقتة عند بدء التشغيل")
        self.auto_clean_cb.setChecked(bool(self.settings.get("auto_clean_temp")))
        layout.addWidget(self.auto_clean_cb)

        self.restore_desc_input = QLineEdit(self.settings.get("restore_point_description") or "")
        form.addRow("وصف نقطة الاستعادة:", self.restore_desc_input)

        self.process_exclusions_input = QLineEdit(
            ", ".join(self.settings.get("process_exclusions") or [])
        )
        form.addRow("عمليات مستثناة من الإنهاء الجماعي:", self.process_exclusions_input)

        self.force_kill_input = QLineEdit(
            ", ".join(self.settings.get("force_kill_list") or [])
        )
        form.addRow("قائمة الإنهاء الإجباري:", self.force_kill_input)

        self.service_exclusions_input = QLineEdit(
            ", ".join(self.settings.get("service_exclusions") or [])
        )
        form.addRow("خدمات مستثناة (مفصولة بفاصلة):", self.service_exclusions_input)

        self.donate_url_input = QLineEdit(self.settings.get("donate_url") or "")
        form.addRow("رابط الدعم المالي:", self.donate_url_input)

        layout.addLayout(form)

        # ---- إدارة المستخدمين (أدمين فقط) ----
        if self.current_user.get("role") == "admin":
            users_box = QGroupBox("إدارة المستخدمين")
            users_layout = QVBoxLayout()

            existing = ", ".join(u["username"] for u in (self.settings.get("users") or []))
            users_layout.addWidget(QLabel(f"الحسابات الحالية: {existing or '—'}"))

            add_form = QFormLayout()
            self.new_username_input = QLineEdit()
            add_form.addRow("اسم مستخدم جديد:", self.new_username_input)
            self.new_password_input = QLineEdit()
            self.new_password_input.setEchoMode(QLineEdit.Password)
            add_form.addRow("كلمة المرور:", self.new_password_input)
            self.new_role_combo = QComboBox()
            self.new_role_combo.addItems(["user", "admin"])
            add_form.addRow("الدور:", self.new_role_combo)
            users_layout.addLayout(add_form)

            btn_add_user = QPushButton("إضافة مستخدم")
            btn_add_user.clicked.connect(self.add_user)
            users_layout.addWidget(btn_add_user)

            users_box.setLayout(users_layout)
            layout.addWidget(users_box)

        # ---- قسم الدعم المالي الاختياري ----
        donate_box = QVBoxLayout()
        donate_msg = self.settings.get("donate_message") or ""
        donate_label = QLabel(donate_msg)
        donate_label.setWordWrap(True)
        donate_box.addWidget(donate_label)

        self.btn_donate = QPushButton("☕ دعم المشروع (اختياري)")
        self.btn_donate.clicked.connect(self.open_donate_link)
        donate_box.addWidget(self.btn_donate)
        layout.addLayout(donate_box)

        # ---- حفظ ----
        btn_save = QPushButton("حفظ الإعدادات")
        btn_save.setObjectName("runButton")
        btn_save.clicked.connect(self.save_and_close)
        layout.addWidget(btn_save)

        self.setLayout(layout)

    def add_user(self):
        username = self.new_username_input.text().strip()
        password = self.new_password_input.text()
        role = self.new_role_combo.currentText()
        try:
            self.auth.create_user(username, password, role=role)
            QMessageBox.information(self, "تم", f"تم إنشاء حساب '{username}' بنجاح.")
            self.new_username_input.clear()
            self.new_password_input.clear()
        except AuthError as e:
            QMessageBox.warning(self, "خطأ", str(e))
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"تعذر إنشاء الحساب: {e}")

    def open_donate_link(self):
        url = self.settings.get("donate_url")
        if not url:
            QMessageBox.information(self, "الدعم", "رابط الدعم غير متوفر حاليًا. شكرًا لاهتمامك!")
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Could not open donate URL: {e}")

    def save_and_close(self):
        # نستخدم save(..., merge=True) دايمًا بدل استبدال كامل الإعدادات.
        process_exclusions = [s.strip() for s in self.process_exclusions_input.text().split(",") if s.strip()]
        force_kill_list = [s.strip() for s in self.force_kill_input.text().split(",") if s.strip()]
        service_exclusions = [s.strip() for s in self.service_exclusions_input.text().split(",") if s.strip()]

        new_settings = {
            "test_mode": self.test_mode_cb.isChecked(),
            "auto_clean_temp": self.auto_clean_cb.isChecked(),
            "restore_point_description": self.restore_desc_input.text().strip() or "Faster PC Restore Point - {date}",
            "process_exclusions": process_exclusions,
            "force_kill_list": force_kill_list,
            "service_exclusions": service_exclusions,
            "donate_url": self.donate_url_input.text().strip(),
        }

        if self.settings.save(new_settings, merge=True):
            self.accept()
        else:
            QMessageBox.warning(self, "خطأ", "تعذر حفظ الإعدادات على القرص. تحقق من صلاحيات الملف.")
