"""
معالج الإعداد الأولي (Setup) — يظهر عند أول تشغيل فقط.

الخطوات:
1) ترحيب وتعريف سريع.
2) إنشاء حساب المدير (إجباري).
3) حماية البرامج: اختيار تطبيقات لا يجوز إغلاقها أبدًا (اختياري).
4) خيارات التثبيت: اختصار سطح المكتب + قائمة ابدأ + التشغيل مع ويندوز +
   استثناء Defender + الوضع التجريبي.
5) المراقبة والتنبيهات.
6) التطبيق: ينفّذ كل ما اختاره المستخدم ويعرض ملخص النتائج.

كل خطوة قابلة للفشل بشكل آمن: أي عملية تثبيت ترجع ActionResult ويُعرض ناتجها
بدل أن تنكسر الواجهة.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from src.gui.theme import COLORS
from src.utils.auth import AuthError
from src.version import APP_NAME, APP_PUBLISHER, APP_VERSION

logger = logging.getLogger(__name__)


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("مرحبًا بك في Faster PC")
        layout = QVBoxLayout(self)
        text = QLabel(
            f"<p><b>Faster PC {APP_VERSION}</b> — أداة صيانة وتسريع ويندوز متكاملة.</p>"
            "<p>هذا المعالج سيجهّز البرنامج خلال خطوات قصيرة:</p>"
            "<ul>"
            "<li>إنشاء حساب المدير (لحماية الإعدادات).</li>"
            "<li>حماية برامجك المهمة من أي إغلاق غير مقصود.</li>"
            "<li>إنشاء اختصارات سطح المكتب وقائمة ابدأ (بالأيقونة الرسمية).</li>"
            "<li>ضبط المراقبة والتنبيهات.</li>"
            "</ul>"
            "<p style='color:%s'>كل الإعدادات قابلة للتغيير لاحقًا من نافذة الإعدادات.</p>"
            % COLORS["text_muted"]
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.RichText)
        layout.addWidget(text)
        layout.addStretch()
        copyright_label = QLabel(f"{APP_PUBLISHER} — {APP_NAME}")
        copyright_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(copyright_label)


class AccountPage(QWizardPage):
    """إنشاء حساب المدير الأول."""

    def __init__(self, settings, auth):
        super().__init__()
        self.settings = settings
        self.auth = auth
        self.setTitle("حساب المدير")
        self.setSubTitle("أنشئ الحساب الذي سيدير البرنامج (يُخزَّن محليًا بشكل مشفّر ولا يُرسل لأي مكان).")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("مثال: yousef")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("8 أحرف على الأقل")
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        form.addRow("اسم المستخدم:", self.username_input)
        form.addRow("كلمة المرور:", self.password_input)
        form.addRow("تأكيد كلمة المرور:", self.confirm_input)
        layout.addLayout(form)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addStretch()

        self.username_input.textChanged.connect(self.completeChanged)
        self.password_input.textChanged.connect(self.completeChanged)
        self.confirm_input.textChanged.connect(self.completeChanged)

    def isComplete(self) -> bool:  # noqa: N802
        return bool(self.username_input.text().strip() and self.password_input.text())

    def validatePage(self) -> bool:  # noqa: N802
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if password != self.confirm_input.text():
            self.hint.setText("<span style='color:#e74c3c'>كلمتا المرور غير متطابقتين.</span>")
            return False
        users = self.settings.get("users") or []
        if any(u.get("username", "").lower() == username.lower() for u in users):
            self.hint.setText("<span style='color:#e74c3c'>اسم المستخدم موجود مسبقًا.</span>")
            return False
        try:
            self.auth.create_user(username, password, role="admin")
        except AuthError as exc:
            self.hint.setText(f"<span style='color:#e74c3c'>{exc}</span>")
            return False
        except Exception as exc:  # pragma: no cover
            logger.exception("Account creation failed")
            self.hint.setText(f"<span style='color:#e74c3c'>تعذر إنشاء الحساب: {exc}</span>")
            return False

        self.settings.set("last_user", username)
        self.hint.setText("<span style='color:#3fbf7f'>تم إنشاء الحساب بنجاح.</span>")
        return True


class ProtectionPage(QWizardPage):
    """اختيار البرامج المحمية (لا يغلقها البرنامج أبدًا)."""

    def __init__(self, protection):
        super().__init__()
        self.protection = protection
        self.setTitle("حماية برامجك المهمة")
        self.setSubTitle(
            "حدّد البرامج التي لا تريد إغلاقها أبدًا (مثل تطبيق الصور، مشغل الوسائط، المتصفح...). "
            "هذه البرامج تُستثنى تلقائيًا من كل عمليات الإنهاء."
        )

        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث عن برنامج...")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self.hint)

        self._populate()

    def _populate(self) -> None:
        try:
            apps = self.protection.list_running_apps()
        except Exception as exc:  # pragma: no cover
            logger.debug("Could not list apps: %s", exc)
            apps = []
        for app in apps[:200]:
            item = QListWidgetItem(f"{app['name']} — {app['memory_mb']} MB")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, app["name"])
            self.list_widget.addItem(item)
        self.hint.setText(
            f"عرض {self.list_widget.count()} برنامجًا يعمل الآن. "
            "تقدر تتخطى هذه الخطوة وتضيف برامج لاحقًا من تبويب 'الحماية'."
        )

    def _apply_filter(self, text: str) -> None:
        text = (text or "").strip().lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item.setHidden(bool(text) and text not in item.text().lower())

    def selected_apps(self) -> list[str]:
        return [
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.Checked
        ]


class OptionsPage(QWizardPage):
    """خيارات التثبيت التي طلبها صاحب المشروع: اختصار سطح المكتب والأيقونة وغيرها."""

    def __init__(self):
        super().__init__()
        self.setTitle("خيارات التثبيت")
        self.setSubTitle("اختر ما تريد تجهيزه تلقائيًا الآن.")

        layout = QVBoxLayout(self)

        self.cb_desktop = QCheckBox("إنشاء اختصار على سطح المكتب (بالأيقونة الرسمية)")
        self.cb_desktop.setChecked(True)
        layout.addWidget(self.cb_desktop)

        self.cb_start_menu = QCheckBox("إضافة اختصار في قائمة ابدأ")
        self.cb_start_menu.setChecked(True)
        layout.addWidget(self.cb_start_menu)

        self.cb_startup = QCheckBox("تشغيل البرنامج تلقائيًا مع بدء ويندوز")
        layout.addWidget(self.cb_startup)

        self.cb_minimized = QCheckBox("البدء مصغّرًا في شريط المهام (بدون نافذة)")
        self.cb_minimized.setChecked(True)
        layout.addWidget(self.cb_minimized)

        self.cb_defender = QCheckBox("إضافة البرنامج إلى استثناءات Windows Defender (يقلل الإنذارات الكاذبة الشائعة)")
        self.cb_defender.setChecked(True)
        layout.addWidget(self.cb_defender)

        note = QLabel(
            "ملاحظة: استثناء Defender اختياري ويُطبَّق على مجلدات البرنامج فقط. "
            "إذا تركتَه بدون تحديد يمكنك تفعيله لاحقًا من الإعدادات."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(note)

        self.cb_test_mode = QCheckBox("بدء البرنامج في الوضع التجريبي (معاينة الإجراءات بدون تنفيذ)")
        layout.addWidget(self.cb_test_mode)

        layout.addStretch()


class MonitoringPage(QWizardPage):
    """إعداد المراقبة والتنبيهات."""

    def __init__(self):
        super().__init__()
        self.setTitle("المراقبة والتنبيهات")
        self.setSubTitle("كيف تريد أن يراقب البرنامج أداء جهازك وينبهك للمشاكل؟")

        layout = QVBoxLayout(self)
        self.cb_monitoring = QCheckBox("تفعيل مراقبة الأداء المباشرة (CPU / RAM / القرص)")
        self.cb_monitoring.setChecked(True)
        layout.addWidget(self.cb_monitoring)

        self.cb_health = QCheckBox("تفعيل مراقبة الأعطال من سجل أحداث ويندوز (انهيار التطبيقات وأخطاء النظام)")
        self.cb_health.setChecked(True)
        layout.addWidget(self.cb_health)

        self.cb_notifications = QCheckBox("عرض التنبيهات (داخل البرنامج وفي شريط المهام)")
        self.cb_notifications.setChecked(True)
        layout.addWidget(self.cb_notifications)

        form = QFormLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(2)
        self.interval_spin.setSuffix(" ثانية")
        form.addRow("تحديث لوحة الأداء كل:", self.interval_spin)

        self.cpu_spin = QSpinBox()
        self.cpu_spin.setRange(50, 100)
        self.cpu_spin.setValue(90)
        self.cpu_spin.setSuffix(" %")
        form.addRow("تنبيه عند استهلاك المعالج فوق:", self.cpu_spin)

        self.ram_spin = QSpinBox()
        self.ram_spin.setRange(50, 100)
        self.ram_spin.setValue(90)
        self.ram_spin.setSuffix(" %")
        form.addRow("تنبيه عند استهلاك الذاكرة فوق:", self.ram_spin)

        layout.addLayout(form)
        layout.addStretch()


class FinishPage(QWizardPage):
    """تنفيذ خيارات التثبيت وعرض ملخص النتائج."""

    def __init__(self, settings, installer, protection, account_page, options_page, monitoring_page, protection_page):
        super().__init__()
        self.settings = settings
        self.installer = installer
        self.protection = protection
        self.account_page = account_page
        self.options_page = options_page
        self.monitoring_page = monitoring_page
        self.protection_page = protection_page
        self.ran = False

        self.setTitle("جاهز للانطلاق")
        self.setSubTitle("سيتم الآن تطبيق اختياراتك. هذه العملية سريعة ولن تظهر أي نوافذ.")
        layout = QVBoxLayout(self)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(220)
        layout.addWidget(self.output)

    def initializePage(self) -> None:  # noqa: N802
        if self.ran:
            return
        self.ran = True
        lines: list[str] = []

        # 1) البرامج المحمية
        protected = self.protection_page.selected_apps()
        for name in protected:
            if self.protection.add_app_to_protection(name):
                lines.append(f"✔ أضيف إلى الحماية: {name}")
        if protected:
            lines.append("")

        # 2) الاختصارات والتشغيل مع ويندوز و Defender
        options = self.options_page
        if options.cb_desktop.isChecked():
            lines.append("• " + self.installer.create_desktop_shortcut().message)
        if options.cb_start_menu.isChecked():
            lines.append("• " + self.installer.create_start_menu_shortcut().message)
        if options.cb_startup.isChecked():
            lines.append("• " + self.installer.set_run_at_startup(True, minimized=options.cb_minimized.isChecked()).message)
        if options.cb_defender.isChecked():
            lines.append("• " + self.installer.add_defender_exclusions().message)

        # 3) المراقبة والتنبيهات
        monitoring = self.monitoring_page
        self.settings.save({
            "test_mode": options.cb_test_mode.isChecked(),
            "monitoring": {
                "enabled": monitoring.cb_monitoring.isChecked(),
                "interval_sec": monitoring.interval_spin.value(),
                "thresholds": {
                    "cpu_percent": monitoring.cpu_spin.value(),
                    "ram_percent": monitoring.ram_spin.value(),
                },
            },
            "health": {"enabled": monitoring.cb_health.isChecked()},
            "notifications": {"enabled": monitoring.cb_notifications.isChecked()},
            "setup_completed": True,
        })
        lines.append("")
        lines.append("• تم حفظ الإعدادات، وتم إكمال الإعداد الأولي بنجاح.")
        if options.cb_test_mode.isChecked():
            lines.append("• الوضع التجريبي مفعّل: يمكنك إيقافه من الإعدادات عند الجاهزية.")

        self.output.setPlainText("\n".join(str(line) for line in lines if line is not None))
        logger.info("First-run setup completed.")


class SetupWizard(QWizard):
    """معالج الإعداد الأولي الكامل."""

    def __init__(self, settings, installer, protection, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"إعداد {APP_NAME} لأول مرة")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setMinimumSize(660, 560)

        account_page = AccountPage(settings, _auth_for(settings))
        options_page = OptionsPage()
        monitoring_page = MonitoringPage()
        protection_page = ProtectionPage(protection)

        self.addPage(WelcomePage())
        self.addPage(account_page)
        self.addPage(protection_page)
        self.addPage(options_page)
        self.addPage(monitoring_page)
        self.addPage(FinishPage(
            settings, installer, protection, account_page,
            options_page, monitoring_page, protection_page,
        ))

        self.setButtonText(QWizard.NextButton, "التالي")
        self.setButtonText(QWizard.BackButton, "السابق")
        self.setButtonText(QWizard.FinishButton, "إنهاء الإعداد")
        self.setButtonText(QWizard.CancelButton, "إلغاء")


def _auth_for(settings):
    from src.utils.auth import AuthManager

    return AuthManager(settings)


def run_setup_if_needed(settings, installer, protection, parent=None) -> bool:
    """يرجع True إذا كان الإعداد مكتملًا (أو أُكمل الآن)، وFalse إذا ألغى المستخدم."""
    from PySide6.QtWidgets import QApplication

    if settings.get("setup_completed"):
        return True
    QApplication.processEvents()
    wizard = SetupWizard(settings, installer, protection, parent)
    result = wizard.exec()
    if result == QWizard.Accepted:
        return True
    return bool(settings.get("setup_completed"))


__all__ = ["SetupWizard", "run_setup_if_needed"]
