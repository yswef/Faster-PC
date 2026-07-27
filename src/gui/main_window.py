import sys
import os
import logging
import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QCheckBox, QLabel, QMessageBox, QTextEdit, QTabWidget,
    QProgressBar, QListWidget, QListWidgetItem, QGridLayout, QGroupBox
)

import psutil

from src.config.settings import SettingsManager
from src.core.optimizer import SystemOptimizer
from src.core.cleaner import SystemCleaner
from src.core.repair import SystemRepair, is_admin
from src.core.tweaks import PerformanceTweaks
from src.utils.logger import UILogHandler, setup_file_logging
from src.utils.workers import TaskWorker
from src.utils.paths import resource_path
from src.gui.settings_window import SettingsWindow
from src.gui.login_window import LoginWindow

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, current_user: dict):
        super().__init__()
        self.current_user = current_user  # {"username": ..., "role": "admin"|"user"}
        self.is_admin_role = current_user.get("role") == "admin"

        self.settings = SettingsManager()
        self.optimizer = SystemOptimizer(self.settings)
        self.cleaner = SystemCleaner(self.settings)
        self.repair = SystemRepair(self.settings)
        self.tweaks = PerformanceTweaks(self.settings)
        self.own_pid = os.getpid()

        self._workers = []
        self.logged_out = False

        self.setWindowTitle(f"Faster PC — {current_user['username']} ({current_user['role']})")
        self.setMinimumSize(640, 640)

        self._build_ui()
        self._apply_stylesheet()
        self._start_dashboard_timer()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout()

        top_bar = QHBoxLayout()
        title = QLabel(f"👤 {self.current_user['username']} ({self.current_user['role']})")
        top_bar.addWidget(title)
        top_bar.addStretch()
        btn_logout = QPushButton("تسجيل الخروج")
        btn_logout.clicked.connect(self.logout)
        top_bar.addWidget(btn_logout)
        root.addLayout(top_bar)

        if not is_admin():
            warn = QLabel("⚠ البرنامج غير مُشغّل بصلاحيات مدير — بعض العمليات (SFC/DISM/الخدمات/نقطة الاستعادة) لن تعمل.")
            warn.setWordWrap(True)
            warn.setStyleSheet("color:#f0ad4e; padding:6px;")
            root.addWidget(warn)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dashboard_tab(), "اللوحة الرئيسية")
        self.tabs.addTab(self._build_clean_tab(), "التنظيف")
        self.tabs.addTab(self._build_optimize_tab(), "التحسين")
        self.tabs.addTab(self._build_services_tab(), "الخدمات")
        self.tabs.addTab(self._build_startup_tab(), "بدء التشغيل")
        self.tabs.addTab(self._build_tweaks_tab(), "تسريع النظام")
        self.tabs.addTab(self._build_repair_tab(), "الإصلاح")
        if self.is_admin_role:
            self.tabs.addTab(self._build_admin_tab(), "لوحة التحكم (قريبًا)")
        root.addWidget(self.tabs)

        root.addWidget(QLabel("سجل العمليات:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(130)
        root.addWidget(self.log_output)

        self._setup_logging()

        bottom = QHBoxLayout()
        self.btn_settings = QPushButton("⚙️ الإعدادات")
        self.btn_settings.clicked.connect(self.open_settings)
        bottom.addWidget(self.btn_settings)
        self.btn_docs = QPushButton("📖 التوثيق")
        self.btn_docs.clicked.connect(self.open_docs)
        bottom.addWidget(self.btn_docs)
        bottom.addStretch()
        root.addLayout(bottom)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def _setup_logging(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        handler = UILogHandler(self.log_output)
        root_logger.addHandler(handler)
        setup_file_logging()
        logging.info(f"Session started as '{self.current_user['username']}' ({self.current_user['role']}).")

    def _apply_stylesheet(self):
        style_path = resource_path("src/gui/styles.qss")
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                QApplication.instance().setStyleSheet(f.read())
        except OSError as e:
            logger.warning(f"Could not load stylesheet ({style_path}): {e}")

    # ------------------------------------------------------------------
    # لوحة رئيسية: استهلاك مباشر (CPU/RAM/Disk) يتحدث كل ثانيتين
    # ------------------------------------------------------------------
    def _build_dashboard_tab(self):
        w = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("استهلاك الموارد المباشر:"))

        grid = QGridLayout()

        grid.addWidget(QLabel("المعالج (CPU):"), 0, 0)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        grid.addWidget(self.cpu_bar, 0, 1)

        grid.addWidget(QLabel("الذاكرة (RAM):"), 1, 0)
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        grid.addWidget(self.ram_bar, 1, 1)

        grid.addWidget(QLabel("القرص C: :"), 2, 0)
        self.disk_bar = QProgressBar()
        self.disk_bar.setRange(0, 100)
        grid.addWidget(self.disk_bar, 2, 1)

        layout.addLayout(grid)

        self.ram_detail_label = QLabel("")
        self.ram_detail_label.setStyleSheet("color:#9a9dab; font-size:12px;")
        layout.addWidget(self.ram_detail_label)

        btn_quick = QPushButton("⚡ تطبيق حزمة التسريع الموصى بها الآن")
        btn_quick.setObjectName("runButton")
        btn_quick.clicked.connect(self.run_apply_recommended_bundle)
        layout.addWidget(btn_quick)

        layout.addStretch()
        w.setLayout(layout)
        return w

    def _start_dashboard_timer(self):
        self.dash_timer = QTimer(self)
        self.dash_timer.timeout.connect(self._refresh_dashboard)
        self.dash_timer.start(2000)
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")

            self.cpu_bar.setValue(int(cpu))
            self.ram_bar.setValue(int(ram.percent))
            self.disk_bar.setValue(int(disk.percent))
            self.ram_detail_label.setText(
                f"{ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB مستخدمة"
            )
        except Exception as e:
            logger.debug(f"Dashboard refresh failed: {e}")

    # ------------------------------------------------------------------
    def _build_clean_tab(self):
        w = QWidget()
        layout = QVBoxLayout()

        self.cb_temp = QCheckBox("تضمين مجلد %TEMP% الشخصي (وليس فقط ملفات ويندوز المؤقتة)")
        layout.addWidget(self.cb_temp)

        btn_clean_temp = QPushButton("تنظيف الملفات المؤقتة")
        btn_clean_temp.setObjectName("runButton")
        btn_clean_temp.clicked.connect(self.run_clean_temp)
        layout.addWidget(btn_clean_temp)

        btn_recycle = QPushButton("إفراغ سلة المحذوفات")
        btn_recycle.clicked.connect(self.run_empty_recycle_bin)
        layout.addWidget(btn_recycle)

        btn_updates = QPushButton("حذف ملفات تحديثات ويندوز القديمة")
        btn_updates.clicked.connect(self.run_clean_updates)
        layout.addWidget(btn_updates)

        layout.addStretch()
        w.setLayout(layout)
        return w

    def _build_optimize_tab(self):
        w = QWidget()
        layout = QVBoxLayout()

        danger_box = QGroupBox("إنهاء كل العمليات غير المستثناة")
        danger_layout = QVBoxLayout()
        danger_layout.addWidget(QLabel(
            "ينهي كل العمليات الجارية ما عدا القائمة بـ process_exclusions بالإعدادات "
            "والعمليات الحرجة لإقلاع ويندوز (لا يمكن إيقافها لأنها تسبب توقف النظام فورًا)."
        ))
        btn_kill_all = QPushButton("🔴 إنهاء كل العمليات غير المستثناة الآن")
        btn_kill_all.clicked.connect(self.run_kill_all_except_excluded)
        danger_layout.addWidget(btn_kill_all)
        danger_box.setLayout(danger_layout)
        layout.addWidget(danger_box)

        btn_kill_list = QPushButton("إنهاء عمليات force_kill_list فقط")
        btn_kill_list.clicked.connect(self.run_kill_processes)
        layout.addWidget(btn_kill_list)

        layout.addWidget(QLabel("أعلى العمليات استهلاكًا للذاكرة:"))
        btn_list = QPushButton("عرض العمليات الأكثر استهلاكًا")
        btn_list.clicked.connect(self.run_list_processes)
        layout.addWidget(btn_list)

        layout.addStretch()
        w.setLayout(layout)
        return w

    def _build_services_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("خدمات ويندوز يمكن إيقافها لتقليل الاستهلاك (يتطلب صلاحيات مدير):"))

        self.services_list = QListWidget()
        for name, desc in self.optimizer.KNOWN_HEAVY_SERVICES.items():
            item = QListWidgetItem(f"{name} — {desc}")
            item.setData(Qt.UserRole, name)
            item.setCheckState(Qt.Unchecked)
            self.services_list.addItem(item)
        layout.addWidget(self.services_list)

        row = QHBoxLayout()
        btn_disable = QPushButton("إيقاف المحدد")
        btn_disable.clicked.connect(lambda: self._apply_service_changes(enable=False))
        row.addWidget(btn_disable)
        btn_enable = QPushButton("تشغيل المحدد")
        btn_enable.clicked.connect(lambda: self._apply_service_changes(enable=True))
        row.addWidget(btn_enable)
        layout.addLayout(row)

        w.setLayout(layout)
        return w

    def _build_startup_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("برامج بدء التشغيل (يمكن تعطيلها/إعادة تفعيلها بأمان):"))

        self.startup_list = QListWidget()
        layout.addWidget(self.startup_list)

        row = QHBoxLayout()
        btn_refresh = QPushButton("تحديث القائمة")
        btn_refresh.clicked.connect(self._refresh_startup_list)
        row.addWidget(btn_refresh)
        btn_toggle = QPushButton("تبديل الحالة للمحدد")
        btn_toggle.clicked.connect(self._toggle_selected_startup_item)
        row.addWidget(btn_toggle)
        layout.addLayout(row)

        w.setLayout(layout)
        self._refresh_startup_list()
        return w

    def _refresh_startup_list(self):
        self.startup_list.clear()
        for item_data in self.optimizer.list_startup_items():
            label = f"{'⛔ [معطّل] ' if item_data['disabled'] else ''}{item_data['name']} ({item_data['hive']})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, item_data)
            self.startup_list.addItem(item)

    def _toggle_selected_startup_item(self):
        item = self.startup_list.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole)
        new_enabled = data["disabled"]  # لو كان معطّل، نفعّله والعكس
        ok = self.optimizer.set_startup_item_enabled(data["name"], data["hive"], enabled=new_enabled)
        if ok:
            logging.info(f"تم تغيير حالة: {data['name']}")
            self._refresh_startup_list()
        else:
            logging.warning(f"تعذر تغيير حالة: {data['name']}")

    def _build_tweaks_tab(self):
        w = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("تحسينات أداء ويندوز:"))

        btn_power = QPushButton("تفعيل خطة الأداء العالي")
        btn_power.clicked.connect(lambda: self._run_tweak(self.tweaks.set_high_performance_power_plan))
        layout.addWidget(btn_power)

        btn_ultimate = QPushButton("فتح وتفعيل خطة 'الأداء المطلق' (Ultimate Performance)")
        btn_ultimate.clicked.connect(lambda: self._run_tweak(self.tweaks.unlock_ultimate_performance))
        layout.addWidget(btn_ultimate)

        btn_visual = QPushButton("ضبط المؤثرات البصرية على 'أفضل أداء'")
        btn_visual.clicked.connect(lambda: self._run_tweak(self.tweaks.set_visual_effects_best_performance))
        layout.addWidget(btn_visual)

        btn_bg_off = QPushButton("تعطيل تطبيقات الخلفية (UWP)")
        btn_bg_off.clicked.connect(lambda: self._run_tweak(lambda: self.tweaks.toggle_background_apps(False)))
        layout.addWidget(btn_bg_off)

        btn_hags = QPushButton("تفعيل جدولة GPU بالعتاد (HAGS) — يحتاج إعادة تشغيل")
        btn_hags.clicked.connect(lambda: self._run_tweak(lambda: self.tweaks.toggle_hardware_gpu_scheduling(True)))
        layout.addWidget(btn_hags)

        adv_box = QGroupBox("متقدم — يقلل الحماية مقابل أداء (اقرأ قبل الاستخدام)")
        adv_layout = QVBoxLayout()
        adv_layout.addWidget(QLabel(
            "تعطيل Memory Integrity يقلل الحماية ضد البرمجيات الخبيثة على مستوى النظام "
            "(rootkits) مقابل تحسين أداء ملحوظ ببعض الألعاب. لا يُفعّل إلا بموافقتك الصريحة."
        ))
        btn_vbs_off = QPushButton("تعطيل Memory Integrity (بعد التأكيد)")
        btn_vbs_off.clicked.connect(self.run_disable_memory_integrity)
        adv_layout.addWidget(btn_vbs_off)
        adv_box.setLayout(adv_layout)
        layout.addWidget(adv_box)

        layout.addStretch()
        w.setLayout(layout)
        return w

    def _build_repair_tab(self):
        w = QWidget()
        layout = QVBoxLayout()

        btn_dns = QPushButton("تفريغ ذاكرة DNS المؤقتة")
        btn_dns.clicked.connect(lambda: self._run_in_background(self.repair.flush_dns, self._log_repair_result))
        layout.addWidget(btn_dns)

        btn_scan = QPushButton("فحص القرص C: (بدون تعطيل)")
        btn_scan.clicked.connect(lambda: self._run_in_background(lambda: self.repair.scan_disk("C:"), self._log_repair_result))
        layout.addWidget(btn_scan)

        btn_restore = QPushButton("إنشاء نقطة استعادة")
        btn_restore.clicked.connect(lambda: self._run_in_background(self.repair.create_restore_point, self._log_repair_result))
        layout.addWidget(btn_restore)

        btn_sfc = QPushButton("فحص وإصلاح ملفات النظام - SFC")
        btn_sfc.clicked.connect(lambda: self._run_in_background(self.repair.run_sfc, self._log_repair_result))
        layout.addWidget(btn_sfc)

        btn_dism = QPushButton("إصلاح صورة النظام - DISM (قد يستغرق وقتًا طويلاً)")
        btn_dism.clicked.connect(lambda: self._run_in_background(self.repair.run_dism, self._log_repair_result))
        layout.addWidget(btn_dism)

        layout.addStretch()
        w.setLayout(layout)
        return w

    def _build_admin_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel(
            "🔧 لوحة تحكم المميزات (قادمة قريبًا)\n\n"
            "ستتيح هذه اللوحة للمدير التحكم بأي ميزة تظهر للمستخدمين، وتفعيل نموذج "
            "مجاني/مدفوع لاحقًا. البنية جاهزة بالفعل عبر feature_flags في config.json — "
            "كل الميزات مفتوحة للجميع حاليًا حتى بناء اللوحة فعليًا."
        ))
        layout.addStretch()
        w.setLayout(layout)
        return w

    # ------------------------------------------------------------------
    def _run_in_background(self, fn, on_success, *args, **kwargs):
        worker = TaskWorker(fn, *args, **kwargs)
        worker.finished_ok.connect(on_success)
        worker.finished_error.connect(lambda err: logging.error(f"فشلت العملية: {err}"))
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self._workers.append(worker)
        worker.start()

    def _run_tweak(self, fn):
        self._run_in_background(fn, self._log_repair_result)

    def _log_repair_result(self, result):
        if getattr(result, "success", False):
            logging.info(result.message)
        else:
            logging.warning(getattr(result, "message", str(result)))

    # ------------------------------------------------------------------
    def run_clean_temp(self):
        include_temp = self.cb_temp.isChecked()
        if include_temp:
            reply = QMessageBox.warning(
                self, "تأكيد", "سيتم حذف ملفات %TEMP% الشخصية. هل أنت متأكد؟",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        logging.info("جاري تنظيف الملفات المؤقتة...")
        self._run_in_background(
            self.cleaner.clean_temp_files,
            lambda r: logging.info(f"تم التنظيف: {r['removed']} محذوف، {r['skipped']} متخطى."),
            include_temp=include_temp,
        )

    def run_empty_recycle_bin(self):
        logging.info("جاري إفراغ سلة المحذوفات...")
        self._run_in_background(self.cleaner.clean_recycle_bin, lambda r: None)

    def run_clean_updates(self):
        reply = QMessageBox.warning(
            self, "تأكيد", "سيتم حذف ذاكرة تحديثات ويندوز المؤقتة. متابعة؟",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        logging.info("جاري حذف ملفات التحديثات القديمة...")
        self._run_in_background(self.cleaner.clean_old_updates, lambda r: None)

    def run_kill_processes(self):
        logging.info("جاري تنفيذ إنهاء عمليات force_kill_list...")
        self._run_in_background(
            self.optimizer.kill_unwanted_processes,
            lambda r: logging.info(f"تم إنهاء: {r['killed']}"),
        )

    def run_kill_all_except_excluded(self):
        reply = QMessageBox.warning(
            self, "تحذير هام",
            "سيتم إنهاء كل العمليات الجارية على جهازك ما عدا المدرجة بـ "
            "process_exclusions بالإعدادات (وعمليات ويندوز الحرجة اللي لا يمكن "
            "إيقافها بأي شكل). أي عمل غير محفوظ ببرامج مفتوحة سيُفقد.\n\n"
            "هل أنت متأكد أنك تريد المتابعة؟",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        logging.warning("جاري إنهاء كل العمليات غير المستثناة...")
        self._run_in_background(
            self.optimizer.kill_all_except_excluded,
            lambda r: logging.info(f"تم إنهاء {len(r['killed'])} عملية."),
            own_pid=self.own_pid,
        )

    def run_list_processes(self):
        procs = self.optimizer.list_high_resource_processes(top_n=10)
        for p in procs:
            logging.info(f"{p['name']} (PID {p['pid']}): {p['memory_mb']} MB")

    def _apply_service_changes(self, enable: bool):
        checked = []
        for i in range(self.services_list.count()):
            item = self.services_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.data(Qt.UserRole))
        if not checked:
            return
        for name in checked:
            ok = self.optimizer.set_service_state(name, enabled=enable)
            action = "تشغيل" if enable else "إيقاف"
            if ok:
                logging.info(f"تم {action} خدمة {name}.")
            else:
                logging.warning(f"تعذر {action} خدمة {name}.")

    def run_apply_recommended_bundle(self):
        logging.info("جاري تطبيق حزمة التسريع الموصى بها...")
        self._run_in_background(
            self.tweaks.apply_recommended_bundle,
            lambda results: [self._log_repair_result(r) for _, r in results],
        )

    def run_disable_memory_integrity(self):
        reply = QMessageBox.warning(
            self, "تأكيد مطلوب",
            "تعطيل Memory Integrity يقلل الحماية ضد البرمجيات الخبيثة على مستوى "
            "النظام (rootkits). هل تفهم المخاطرة وتريد المتابعة؟ (يتطلب إعادة تشغيل)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._run_in_background(
            lambda: self.tweaks.toggle_memory_integrity(False, confirm=True),
            self._log_repair_result,
        )

    # ------------------------------------------------------------------
    def open_settings(self):
        SettingsWindow(self.settings, current_user=self.current_user).exec()

    def open_docs(self):
        docs_path = resource_path("docs/docs.html")
        try:
            webbrowser.open(f"file://{docs_path}")
        except Exception as e:
            logger.warning(f"Could not open docs: {e}")
            QMessageBox.information(self, "التوثيق", f"افتح هذا الملف يدويًا:\n{docs_path}")

    def logout(self):
        self.logged_out = True
        self.close()


def launch_app():
    app = QApplication(sys.argv)

    while True:
        settings = SettingsManager()
        login = LoginWindow(settings)
        if login.exec() != LoginWindow.Accepted or login.authenticated_user is None:
            sys.exit(0)

        window = MainWindow(login.authenticated_user)
        window.show()
        app.exec()

        if not window.logged_out:
            break  # المستخدم أغلق النافذة عاديًا، مو تسجيل خروج

    sys.exit(0)


if __name__ == "__main__":
    launch_app()
