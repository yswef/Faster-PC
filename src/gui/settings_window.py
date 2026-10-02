"""
نافذة الإعدادات — كل خيارات البرنامج في مكان واحد، مقسّمة تبويبات واضحة.

أي تغيير هنا يُحفظ فور الضغط على "حفظ" (مع نسخة احتياطية تلقائية)، ثم يُبلَّغ
المستخدم بنتيجة الحفظ، ويُعاد ضبط خدمات المراقبة حسب الإعدادات الجديدة.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.theme import COLORS
from src.utils.paths import app_data_dir, logs_dir
from src.version import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)


class SettingsWindow(QDialog):
    """نافذة إعدادات البرنامج."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.settings = ctx.settings
        self.setWindowTitle(f"إعدادات {APP_NAME}")
        self.setMinimumSize(680, 620)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_general(), "عام")
        self.tabs.addTab(self._tab_monitoring(), "المراقبة")
        self.tabs.addTab(self._tab_health(), "الأعطال والصحة")
        self.tabs.addTab(self._tab_notifications(), "التنبيهات")
        self.tabs.addTab(self._tab_startup(), "التشغيل والاختصارات")
        self.tabs.addTab(self._tab_protection(), "الحماية")
        self.tabs.addTab(self._tab_advanced(), "متقدم")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("حفظ", QDialogButtonBox.AcceptRole)
        save_btn.setObjectName("primaryButton")
        buttons.addButton("إلغاء", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

    # ------------------------------------------------------------------
    def _spin(self, value: int, low: int, high: int, suffix: str = "") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(int(value))
        if suffix:
            spin.setSuffix(f" {suffix}")
        return spin

    @staticmethod
    def _muted(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        return label

    # ------------------------------------------------------------------
    def _tab_general(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.cb_test_mode = QCheckBox("الوضع التجريبي (تسجيل الإجراءات بدون تنفيذ فعلي)")
        self.cb_test_mode.setChecked(bool(self.settings.get("test_mode")))
        layout.addWidget(self.cb_test_mode)
        layout.addWidget(self._muted("عند تفعيله، كل عملية تُسجَّل بـ '[وضع المعاينة] كان سيتم ...' بدون أي تعديل حقيقي."))

        self.cb_auto_clean = QCheckBox("تنظيف الملفات المؤقتة تلقائيًا عند بدء التشغيل")
        self.cb_auto_clean.setChecked(bool(self.settings.get("auto_clean_temp")))
        layout.addWidget(self.cb_auto_clean)

        form = QFormLayout()
        self.restore_desc = QLineEdit(str(self.settings.get("restore_point_description") or ""))
        form.addRow("وصف نقطة الاستعادة:", self.restore_desc)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["ar", "en"])
        appearance = self.settings.get("appearance") or {}
        self.language_combo.setCurrentText(appearance.get("language", "ar"))
        form.addRow("لغة الواجهة (يُطبّق عند إعادة التشغيل):", self.language_combo)

        self.donate_url_input = QLineEdit(str(self.settings.get("donate_url") or ""))
        form.addRow("رابط الدعم (اختياري):", self.donate_url_input)
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _tab_monitoring(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        section = self.settings.section("monitoring")
        thresholds = section.get("thresholds") or {}

        self.cb_monitoring = QCheckBox("تفعيل مراقبة الأداء المباشرة")
        self.cb_monitoring.setChecked(bool(section.get("enabled", True)))
        layout.addWidget(self.cb_monitoring)

        form = QFormLayout()
        self.spin_interval = self._spin(section.get("interval_sec", 2), 1, 60, "ثانية")
        form.addRow("تحديث اللوحة كل:", self.spin_interval)
        self.spin_history = self._spin(section.get("history_seconds", 300), 60, 3600, "ثانية")
        form.addRow("طول الرسم البياني:", self.spin_history)
        self.spin_top = self._spin(section.get("top_processes", 8), 3, 30)
        form.addRow("عدد العمليات المعروضة:", self.spin_top)
        layout.addLayout(form)

        thresholds_box = QGroupBox("حدود التنبيه")
        tform = QFormLayout(thresholds_box)
        self.spin_cpu = self._spin(thresholds.get("cpu_percent", 90), 10, 100, "%")
        tform.addRow("تنبيه عند استهلاك المعالج فوق:", self.spin_cpu)
        self.spin_ram = self._spin(thresholds.get("ram_percent", 90), 10, 100, "%")
        tform.addRow("تنبيه عند استهلاك الذاكرة فوق:", self.spin_ram)
        self.spin_disk = self._spin(thresholds.get("disk_percent", 90), 10, 100, "%")
        tform.addRow("تنبيه عند امتلاء القرص فوق:", self.spin_disk)
        self.spin_sustained = self._spin(thresholds.get("sustained_seconds", 15), 3, 600, "ثانية")
        tform.addRow("مدة استمرار التجاوز قبل التنبيه:", self.spin_sustained)
        layout.addWidget(thresholds_box)

        self.cb_notify_threshold = QCheckBox("إظهار تنبيه عند تجاوز الحدود")
        self.cb_notify_threshold.setChecked(bool(section.get("notify_on_threshold", True)))
        layout.addWidget(self.cb_notify_threshold)

        self.cb_track_events = QCheckBox("رصد فتح/إغلاق العمليات (لاستكشاف البرامج الثقيلة)")
        self.cb_track_events.setChecked(bool(section.get("track_process_events", True)))
        layout.addWidget(self.cb_track_events)
        layout.addStretch()
        return page

    def _tab_health(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        section = self.settings.section("health")

        self.cb_health = QCheckBox("تفعيل مراقبة الأعطال وصحة النظام")
        self.cb_health.setChecked(bool(section.get("enabled", True)))
        layout.addWidget(self.cb_health)

        form = QFormLayout()
        self.spin_health_interval = self._spin(section.get("check_interval_min", 30), 5, 240, "دقيقة")
        form.addRow("فحص دوري كل:", self.spin_health_interval)
        self.spin_low_disk = self._spin(section.get("low_disk_gb", 5), 1, 100, "GB")
        form.addRow("تنبيه عند بقاء أقل من:", self.spin_low_disk)
        layout.addLayout(form)

        self.cb_watch_event_log = QCheckBox("قراءة سجل أحداث ويندوز (انهيارات التطبيقات وأخطاء النظام)")
        self.cb_watch_event_log.setChecked(bool(section.get("watch_event_log", True)))
        layout.addWidget(self.cb_watch_event_log)

        self.cb_notify_crashes = QCheckBox("إشعار فوري عند اكتشاف عطل جديد")
        self.cb_notify_crashes.setChecked(bool(section.get("notify_crashes", True)))
        layout.addWidget(self.cb_notify_crashes)

        layout.addWidget(self._muted(
            "القراءة من سجل أحداث ويندوز تتم عبر PowerShell بصمت وبدون أي نافذة، وبدون تغيير أي إعداد."
        ))
        layout.addStretch()
        return page

    def _tab_notifications(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        section = self.settings.section("notifications")

        self.cb_notifications = QCheckBox("تفعيل التنبيهات")
        self.cb_notifications.setChecked(bool(section.get("enabled", True)))
        layout.addWidget(self.cb_notifications)

        self.cb_toast = QCheckBox("إظهار تنبيهات شريط المهام (Desktop Toast)")
        self.cb_toast.setChecked(bool(section.get("tray_toast", True)))
        layout.addWidget(self.cb_toast)

        self.cb_in_app = QCheckBox("إظهار التنبيهات داخل البرنامج")
        self.cb_in_app.setChecked(bool(section.get("show_in_app", True)))
        layout.addWidget(self.cb_in_app)

        layout.addWidget(self._muted("تنبيهات الأخطاء الحرجة لا تُكتم أبدًا حتى لو أُوقفت التنبيهات."))
        layout.addStretch()
        return page

    def _tab_startup(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        section = self.settings.section("startup")

        self.cb_run_with_windows = QCheckBox("تشغيل البرنامج تلقائيًا عند بدء ويندوز")
        self.cb_run_with_windows.setChecked(bool(section.get("run_with_windows", False)))
        self.cb_run_with_windows.toggled.connect(self._on_run_with_windows_toggled)
        layout.addWidget(self.cb_run_with_windows)

        self.cb_start_minimized = QCheckBox("البدء مصغّرًا بدون إظهار النافذة")
        self.cb_start_minimized.setChecked(bool(section.get("start_minimized", False)))
        layout.addWidget(self.cb_start_minimized)

        self.cb_minimize_tray = QCheckBox("عند إغلاق النافذة يبقى البرنامج في شريط المهام (بدل الإغلاق)")
        self.cb_minimize_tray.setChecked(bool(section.get("minimize_to_tray_on_close", True)))
        layout.addWidget(self.cb_minimize_tray)

        shortcuts_box = QGroupBox("الاختصارات")
        box_layout = QVBoxLayout(shortcuts_box)
        self.shortcut_status = QLabel("")
        box_layout.addWidget(self.shortcut_status)

        row = QHBoxLayout()
        btn_desktop = QPushButton("إنشاء اختصار سطح المكتب")
        btn_desktop.clicked.connect(self._create_desktop_shortcut)
        row.addWidget(btn_desktop)
        btn_start_menu = QPushButton("إنشاء اختصار قائمة ابدأ")
        btn_start_menu.clicked.connect(self._create_start_menu_shortcut)
        row.addWidget(btn_start_menu)
        btn_remove = QPushButton("حذف الاختصارات")
        btn_remove.clicked.connect(self._remove_shortcuts)
        row.addWidget(btn_remove)
        row.addStretch()
        box_layout.addLayout(row)
        layout.addWidget(shortcuts_box)

        defender_box = QGroupBox("Windows Defender")
        defender_layout = QVBoxLayout(defender_box)
        defender_layout.addWidget(self._muted(
            "إضافة مجلدات البرنامج إلى استثناءات Defender (اختياري — يقلل الإنذارات الكاذبة المعروفة "
            "ضد برامج PyInstaller غير الموقّعة)."
        ))
        drow = QHBoxLayout()
        btn_def_add = QPushButton("إضافة الاستثناءات")
        btn_def_add.clicked.connect(self._add_defender)
        drow.addWidget(btn_def_add)
        btn_def_remove = QPushButton("إزالة الاستثناءات")
        btn_def_remove.clicked.connect(self._remove_defender)
        drow.addWidget(btn_def_remove)
        drow.addStretch()
        defender_layout.addLayout(drow)
        layout.addWidget(defender_box)

        layout.addStretch()
        self._refresh_shortcut_status()
        return page

    def _tab_protection(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.exclusions_list = QListWidget()
        for name in sorted(self.settings.get("process_exclusions") or [], key=str.lower):
            self.exclusions_list.addItem(name)
        layout.addWidget(QLabel("البرامج المستثناة من كل عمليات الإنهاء:"))
        layout.addWidget(self.exclusions_list, 1)

        row = QHBoxLayout()
        btn_add = QPushButton("إضافة استثناء")
        btn_add.clicked.connect(self._add_exclusion)
        row.addWidget(btn_add)
        btn_remove = QPushButton("إزالة المحدد")
        btn_remove.clicked.connect(self._remove_exclusion)
        row.addWidget(btn_remove)
        btn_defaults = QPushButton("إرجاع القائمة الافتراضية")
        btn_defaults.clicked.connect(self._reset_exclusions)
        row.addWidget(btn_defaults)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(self._muted(
            "ملاحظة: عمليات النواة والإقلاع محمية دائمًا ولا تظهر هنا. "
            "لإدارة تطبيقاتك المحمية استخدم تبويب 'الحماية والاستثناءات' في النافذة الرئيسية."
        ))
        return page

    def _tab_advanced(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel(
            f"<b>الإصدار:</b> {APP_VERSION}<br>"
            f"<b>مجلد البيانات:</b> {app_data_dir()}<br>"
            f"<b>مجلد السجلات:</b> {logs_dir()}"
        )
        info.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        btn_open_data = QPushButton("فتح مجلد البيانات")
        btn_open_data.clicked.connect(self._open_data_folder)
        row.addWidget(btn_open_data)
        btn_open_logs = QPushButton("فتح مجلد السجلات")
        btn_open_logs.clicked.connect(self._open_logs_folder)
        row.addWidget(btn_open_logs)
        row.addStretch()
        layout.addLayout(row)

        danger_box = QGroupBox("النسخ الاحتياطي والاستعادة")
        danger_layout = QVBoxLayout(danger_box)
        danger_layout.addWidget(self._muted(
            "البرنامج يحفظ نسخة احتياطية تلقائيًا (config.json.bak) قبل كل حفظ للإعدادات."
        ))
        brow = QHBoxLayout()
        btn_backup = QPushButton("حفظ نسخة احتياطية الآن")
        btn_backup.clicked.connect(self._backup_now)
        brow.addWidget(btn_backup)
        btn_restore = QPushButton("استعادة النسخة الاحتياطية")
        btn_restore.clicked.connect(self._restore_backup)
        brow.addWidget(btn_restore)
        brow.addStretch()
        danger_layout.addLayout(brow)
        layout.addWidget(danger_box)

        reset_box = QGroupBox("إعادة التعيين")
        reset_layout = QVBoxLayout(reset_box)
        reset_layout.addWidget(self._muted(
            "إعادة تعيين الإعدادات ترجع كل الخيارات للقيم الافتراضية (لا تحذف الحسابات ولا سجل التغييرات)."
        ))
        btn_reset = QPushButton("إعادة تعيين الإعدادات للافتراضي")
        btn_reset.setObjectName("dangerButton")
        btn_reset.clicked.connect(self._reset_settings)
        reset_layout.addWidget(btn_reset)
        layout.addWidget(reset_box)

        layout.addStretch()
        self.advanced_hint = QLabel("")
        self.advanced_hint.setWordWrap(True)
        layout.addWidget(self.advanced_hint)
        return page

    # ------------------------------------------------------------------
    # أفعال مساعدة
    # ------------------------------------------------------------------
    def _on_run_with_windows_toggled(self, checked: bool) -> None:
        result = self.ctx.installer.set_run_at_startup(checked, minimized=self.cb_start_minimized.isChecked())
        self.hint.setText(result.message)

    def _create_desktop_shortcut(self) -> None:
        result = self.ctx.installer.create_desktop_shortcut()
        self.hint.setText(result.message)
        self._refresh_shortcut_status()

    def _create_start_menu_shortcut(self) -> None:
        result = self.ctx.installer.create_start_menu_shortcut()
        self.hint.setText(result.message)
        self._refresh_shortcut_status()

    def _remove_shortcuts(self) -> None:
        result = self.ctx.installer.remove_shortcuts()
        self.hint.setText(result.message)
        self._refresh_shortcut_status()

    def _add_defender(self) -> None:
        self.hint.setText(self.ctx.installer.add_defender_exclusions().message)

    def _remove_defender(self) -> None:
        self.hint.setText(self.ctx.installer.remove_defender_exclusions().message)

    def _refresh_shortcut_status(self) -> None:
        summary = self.ctx.installer.installation_summary()
        self.shortcut_status.setText(
            f"سطح المكتب: {'✔ موجود' if summary['desktop_shortcut'] else '✘ غير موجود'} | "
            f"قائمة ابدأ: {'✔ موجود' if summary['start_menu_shortcut'] else '✘ غير موجود'} | "
            f"التشغيل مع ويندوز: {'✔ مفعّل' if summary['run_with_windows'] else '✘ معطّل'}"
        )

    def _add_exclusion(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "استثناء", "اسم العملية (مثال: myapp.exe):")
        if ok and name.strip():
            self.settings.add_process_exclusion(name.strip())
            self.exclusions_list.addItem(name.strip())

    def _remove_exclusion(self) -> None:
        item = self.exclusions_list.currentItem()
        if item is None:
            return
        self.settings.remove_process_exclusion(item.text())
        self.exclusions_list.takeItem(self.exclusions_list.row(item))

    def _reset_exclusions(self) -> None:
        self.settings.reset_section("process_exclusions")
        self.exclusions_list.clear()
        for name in sorted(self.settings.get("process_exclusions") or [], key=str.lower):
            self.exclusions_list.addItem(name)
        self.hint.setText("أُرجعت قائمة الاستثناءات الافتراضية.")

    def _open_data_folder(self) -> None:
        self._open_folder(app_data_dir())

    def _open_logs_folder(self) -> None:
        self._open_folder(logs_dir())

    @staticmethod
    def _open_folder(folder: str) -> None:
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                os.system(f'xdg-open "{folder}" >/dev/null 2>&1 &')
        except Exception:
            pass

    def _backup_now(self) -> None:
        self.hint.setText("تم حفظ نسخة احتياطية." if self.settings.backup_now() else "تعذر حفظ النسخة الاحتياطية.")

    def _restore_backup(self) -> None:
        self.hint.setText(
            "تمت استعادة النسخة الاحتياطية." if self.settings.restore_backup() else "لا توجد نسخة احتياطية."
        )

    def _reset_settings(self) -> None:
        reply = QMessageBox.question(
            self, "تأكيد", "سيتم إرجاع كل الإعدادات للقيم الافتراضية. متابعة؟",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        defaults = {key: value for key, value in self.settings.defaults.items()
                    if key not in ("users", "setup_completed")}
        self.settings.save(defaults, merge=False)
        self.hint.setText("أُعيدت الإعدادات للافتراضي. أعد فتح النافذة لرؤية القيم.")
        logger.info("Settings reset to defaults.")

    # ------------------------------------------------------------------
    def save_and_close(self) -> None:
        monitoring = {
            "enabled": self.cb_monitoring.isChecked(),
            "interval_sec": self.spin_interval.value(),
            "history_seconds": self.spin_history.value(),
            "top_processes": self.spin_top.value(),
            "notify_on_threshold": self.cb_notify_threshold.isChecked(),
            "track_process_events": self.cb_track_events.isChecked(),
            "thresholds": {
                "cpu_percent": self.spin_cpu.value(),
                "ram_percent": self.spin_ram.value(),
                "disk_percent": self.spin_disk.value(),
                "sustained_seconds": self.spin_sustained.value(),
            },
        }
        health = {
            "enabled": self.cb_health.isChecked(),
            "check_interval_min": self.spin_health_interval.value(),
            "low_disk_gb": self.spin_low_disk.value(),
            "watch_event_log": self.cb_watch_event_log.isChecked(),
            "notify_crashes": self.cb_notify_crashes.isChecked(),
        }
        notifications = {
            "enabled": self.cb_notifications.isChecked(),
            "tray_toast": self.cb_toast.isChecked(),
            "show_in_app": self.cb_in_app.isChecked(),
        }
        startup = {
            "run_with_windows": self.cb_run_with_windows.isChecked(),
            "start_minimized": self.cb_start_minimized.isChecked(),
            "minimize_to_tray_on_close": self.cb_minimize_tray.isChecked(),
        }
        data = {
            "test_mode": self.cb_test_mode.isChecked(),
            "auto_clean_temp": self.cb_auto_clean.isChecked(),
            "restore_point_description": self.restore_desc.text().strip() or "Faster PC Restore Point - {date}",
            "appearance": {"language": self.language_combo.currentText()},
            "donate_url": self.donate_url_input.text().strip(),
            "monitoring": monitoring,
            "health": health,
            "notifications": notifications,
            "startup": startup,
        }
        if not self.settings.save(data, merge=True):
            QMessageBox.warning(self, "خطأ", "تعذر حفظ الإعدادات على القرص. تحقق من صلاحيات الملف.")
            return
        self.ctx.monitor.apply_settings()
        self.ctx.health.apply_settings()
        self.accept()


__all__ = ["SettingsWindow"]
