"""
النافذة الرئيسية — كل تبويبات البرنامج وإدارة المهام والأيقونة ومركز التنبيهات.

مبادئ:
- أي عملية ثقيلة تُنفَّذ في خيط منفصل عبر TaskManager (الواجهة لا تتجمد).
- كل نتيجة عملية تُعرض برسالة عربية واضحة + تُسجَّل في السجل والتنبيهات.
- الإغلاق يحوّل الأيقونة لشريط المهام بدل إنهاء البرنامج (قابل للتغيير من الإعدادات).
"""

from __future__ import annotations

import logging
import os
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.app_context import AppContext
from src.core.results import ActionResult
from src.gui.dialogs import (
    AboutDialog,
    ConfirmDialog,
    NotificationsCenterDialog,
    ProtectionPickerDialog,
    TextReportDialog,
)
from src.gui.settings_window import SettingsWindow
from src.gui.theme import COLORS, stylesheet
from src.gui.widgets import Card, SectionHeader, StatCard, ToastManager  # noqa: F401
from src.utils.logger import UILogHandler, read_log_tail
from src.utils.paths import human_size, logs_dir, resource_path
from src.utils.winapi import is_admin
from src.version import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)


def load_app_icon() -> QIcon:
    """أيقونة البرنامج الرسمية (ico على ويندوز، png بديلًا)."""
    for name in ("assets/app_icon.ico", "assets/icon_256.png"):
        path = resource_path(name)
        if os.path.exists(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    return QIcon()


class MainWindow(QMainWindow):
    """النافذة الرئيسية لكل وظائف Faster PC."""

    def __init__(self, ctx: AppContext, current_user: dict, start_minimized: bool = False):
        super().__init__()
        self.ctx = ctx
        self.current_user = current_user or {"username": "?", "role": "user"}
        self.is_admin_role = self.current_user.get("role") == "admin"
        self.logged_out = False
        self._tray_notice_shown = False
        self._tasks = 0
        self._net_history = deque(maxlen=150)
        self._browser_folder = ""

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — {self.current_user['username']}")
        self.setWindowIcon(load_app_icon())
        self.setMinimumSize(1000, 680)
        self.resize(1120, 760)

        self.toasts = ToastManager(self)

        self._build_ui()
        self._apply_style()
        self._build_tray()
        self._connect_signals()

        if self.ctx.monitor.enabled:
            self._refresh_dashboard(self.ctx.monitor.last_sample or self.ctx.monitor.collect())
        self.ctx.start_background_services()

        if start_minimized and self.tray.isVisible():
            self.hide()

    # ==================================================================
    # بناء الواجهة
    # ==================================================================
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_dashboard(), "لوحة الأداء")
        self.tabs.addTab(self._tab_clean(), "التنظيف")
        self.tabs.addTab(self._tab_processes(), "العمليات")
        self.tabs.addTab(self._tab_services(), "الخدمات")
        self.tabs.addTab(self._tab_startup(), "بدء التشغيل")
        self.tabs.addTab(self._tab_tweaks(), "تسريع النظام")
        self.tabs.addTab(self._tab_protection(), "الحماية والاستثناءات")
        self.tabs.addTab(self._tab_health(), "الأعطال والصحة")
        self.tabs.addTab(self._tab_journal(), "سجل التغييرات")
        self.tabs.addTab(self._tab_logs(), "سجل العمليات")
        if self.is_admin_role:
            self.tabs.addTab(self._tab_users(), "المستخدمون")
        root.addWidget(self.tabs, 1)

        root.addWidget(self._build_bottom_bar())
        self.setCentralWidget(central)

        # شريط الحالة
        self.status = QStatusBar()
        self.status.setSizeGripEnabled(False)
        self.setStatusBar(self.status)
        self.status_label = QLabel("")
        self.status.addWidget(self.status_label, 1)
        self.admin_badge = QLabel()
        self.status.addPermanentWidget(self.admin_badge)
        self.test_badge = QLabel()
        self.status.addPermanentWidget(self.test_badge)
        self._update_badges()

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("headerBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel(f"<b style='font-size:16px'>{APP_NAME}</b> "
                       f"<span style='color:{COLORS['success']}'>{APP_VERSION}</span>")
        layout.addWidget(title)
        layout.addSpacing(12)
        user = QLabel(f"👤 {self.current_user['username']}")
        layout.addWidget(user)
        layout.addStretch()

        self.busy_label = QLabel("")
        self.busy_label.setStyleSheet(f"color: {COLORS['warning']};")
        layout.addWidget(self.busy_label)

        btn_logout = QPushButton("تسجيل الخروج")
        btn_logout.clicked.connect(self.logout)
        layout.addWidget(btn_logout)
        return frame

    def _build_bottom_bar(self) -> QWidget:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(2, 0, 2, 0)

        self.btn_notifications = QPushButton("🔔 التنبيهات (0)")
        self.btn_notifications.clicked.connect(self.open_notifications)
        layout.addWidget(self.btn_notifications)

        btn_settings = QPushButton("⚙ الإعدادات")
        btn_settings.clicked.connect(self.open_settings)
        layout.addWidget(btn_settings)

        btn_docs = QPushButton("📖 التوثيق")
        btn_docs.clicked.connect(self.open_docs)
        layout.addWidget(btn_docs)

        btn_about = QPushButton("ℹ حول البرنامج")
        btn_about.clicked.connect(lambda: AboutDialog(self).exec())
        layout.addWidget(btn_about)

        layout.addStretch()
        self.last_result_label = QLabel("")
        self.last_result_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self.last_result_label)
        return frame

    def _apply_style(self) -> None:
        self.setStyleSheet(stylesheet())

    # ==================================================================
    # التبويبات
    # ==================================================================
    def _tab_dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        cards = QGridLayout()
        self.card_cpu = StatCard("المعالج (CPU)", color=COLORS["accent"])
        self.card_ram = StatCard("الذاكرة (RAM)", color=COLORS["purple"])
        self.card_disk = StatCard("قرص النظام", color=COLORS["success"])
        self.card_net = StatCard("الشبكة (تنزيل)", unit=" KB/s", color=COLORS["warning"])
        cards.addWidget(self.card_cpu, 0, 0)
        cards.addWidget(self.card_ram, 0, 1)
        cards.addWidget(self.card_disk, 0, 2)
        cards.addWidget(self.card_net, 0, 3)
        layout.addLayout(cards)

        info_card = Card("معلومات النظام")
        self.sys_info_label = QLabel("جاري القراءة...")
        self.sys_info_label.setWordWrap(True)
        self.sys_info_label.setTextFormat(Qt.RichText)
        info_card.add(self.sys_info_label)
        layout.addWidget(info_card)

        actions = Card("إجراءات سريعة")
        row = QHBoxLayout()
        btn_bundle = QPushButton("⚡ تطبيق حزمة التسريع الموصى بها")
        btn_bundle.setObjectName("primaryButton")
        btn_bundle.clicked.connect(self.run_recommended_bundle)
        row.addWidget(btn_bundle)

        btn_quick_clean = QPushButton("🧹 تنظيف الملفات المؤقتة")
        btn_quick_clean.clicked.connect(lambda: self.run_clean_temp(silent=True))
        row.addWidget(btn_quick_clean)

        btn_scan = QPushButton("🩺 فحص الصحة الآن")
        btn_scan.clicked.connect(self.run_health_scan)
        row.addWidget(btn_scan)
        row.addStretch()
        actions.add_layout(row)
        layout.addWidget(actions)

        procs_card = Card("أعلى العمليات استهلاكًا (لحظيًا)")
        self.dash_procs = self._make_table(["العملية", "PID", "المعالج %", "الذاكرة MB", "محمية"])
        procs_card.add(self.dash_procs)
        layout.addWidget(procs_card, 1)
        return page

    def _tab_clean(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.temp_card = Card("الملفات المؤقتة")
        self.temp_size_label = QLabel("اضغط 'حساب الحجم' لمعرفة المساحة القابلة للاسترجاع.")
        self.cb_user_temp = QCheckBox("تضمين مجلد المستخدم %TEMP% (قد تكون فيه ملفات برامج مفتوحة)")
        row = QHBoxLayout()
        btn_estimate = QPushButton("حساب الحجم")
        btn_estimate.clicked.connect(self.run_estimate_temp)
        row.addWidget(btn_estimate)
        btn_clean = QPushButton("تنظيف الآن")
        btn_clean.setObjectName("primaryButton")
        btn_clean.clicked.connect(lambda: self.run_clean_temp(silent=False))
        row.addWidget(btn_clean)
        row.addStretch()
        self.temp_card.add(self.temp_size_label)
        self.temp_card.add(self.cb_user_temp)
        self.temp_card.add_layout(row)
        layout.addWidget(self.temp_card)

        recycle_card = Card("سلة المحذوفات")
        self.recycle_label = QLabel("—")
        btn_recycle_size = QPushButton("عرض الحجم")
        btn_recycle_size.clicked.connect(self.run_recycle_size)
        btn_recycle = QPushButton("إفراغ السلة")
        btn_recycle.setObjectName("dangerButton")
        btn_recycle.clicked.connect(self.run_empty_recycle_bin)
        rrow = QHBoxLayout()
        rrow.addWidget(btn_recycle_size)
        rrow.addWidget(btn_recycle)
        rrow.addStretch()
        recycle_card.add(self.recycle_label)
        recycle_card.add_layout(rrow)
        layout.addWidget(recycle_card)

        updates_card = Card("مخلفات تحديثات ويندوز")
        updates_card.add(QLabel("تفريغ مجلد تحديثات ويندوز المؤقت مع إيقاف خدمات التحديث ثم إعادة تشغيلها تلقائيًا."))
        btn_updates = QPushButton("تفريغ مخلفات التحديثات")
        btn_updates.clicked.connect(self.run_clean_updates)
        updates_card.add(btn_updates)
        layout.addWidget(updates_card)

        browser_card = Card("كاش المتصفح (Chromium)")
        browser_card.add(QLabel(
            "حدد مجلد بيانات المتصفح المحلي (عادة داخل Local AppData) لتنظيف مجلد الكاش فقط. "
            "لا يُحذف أي كوكيز أو كلمات مرور أو سجل تصفح إطلاقًا."
        ))
        self.browser_path_label = QLabel("لم يتم تحديد مجلد المتصفح.")
        self.browser_path_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.browser_path_label.setWordWrap(True)
        browser_card.add(self.browser_path_label)
        brow = QHBoxLayout()
        btn_pick_browser = QPushButton("اختيار مجلد المتصفح...")
        btn_pick_browser.clicked.connect(self.pick_browser_folder)
        brow.addWidget(btn_pick_browser)
        btn_clean_browser = QPushButton("تنظيف الكاش")
        btn_clean_browser.clicked.connect(self.run_clean_browser_cache)
        brow.addWidget(btn_clean_browser)
        brow.addStretch()
        browser_card.add_layout(brow)
        layout.addWidget(browser_card)

        reports_card = Card("تقارير الأعطال والذاكرة المؤقتة للانهيارات")
        reports_card.add(QLabel("حذف ملفات تقارير الأخطاء (WER) وملفات CrashDumps التابعة لحسابك."))
        btn_reports = QPushButton("تنظيف تقارير الأعطال")
        btn_reports.clicked.connect(self.run_clean_reports)
        reports_card.add(btn_reports)
        layout.addWidget(reports_card)

        layout.addStretch()
        return page

    def _tab_processes(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.procs_card = Card("العمليات الجارية")
        self.procs_table = self._make_table(
            ["العملية", "PID", "المعالج %", "الذاكرة MB", "الحماية"]
        )
        self.procs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.procs_card.add(self.procs_table)

        row = QHBoxLayout()
        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self.refresh_process_table)
        row.addWidget(btn_refresh)

        btn_kill_selected = QPushButton("إنهاء العملية المحددة")
        btn_kill_selected.clicked.connect(self.run_kill_selected_process)
        row.addWidget(btn_kill_selected)

        btn_force_list = QPushButton("إنهاء قائمة الإنهاء المحددة")
        btn_force_list.clicked.connect(self.run_kill_force_list)
        row.addWidget(btn_force_list)

        btn_protect = QPushButton("🛡 حماية برنامج...")
        btn_protect.clicked.connect(self.add_protection_from_picker)
        row.addWidget(btn_protect)

        btn_kill_all = QPushButton("⛔ إنهاء كل العمليات غير المستثناة")
        btn_kill_all.setObjectName("dangerButton")
        btn_kill_all.clicked.connect(self.run_kill_all_except_excluded)
        row.addWidget(btn_kill_all)
        row.addStretch()
        self.procs_card.add_layout(row)

        self.protection_summary_label = QLabel("")
        self.protection_summary_label.setWordWrap(True)
        self.procs_card.add(self.protection_summary_label)
        layout.addWidget(self.procs_card, 1)

        self._update_protection_summary()
        return page

    def _tab_services(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "خدمات ويندوز الشائعة الاستهلاك. الحالة ونوع التشغيل يُقرآن مباشرة من النظام، "
            "والخدمات المحمية لا يمكن إيقافها إطلاقًا."
        ))

        self.services_table = self._make_table(
            ["الخدمة", "الحالة", "نوع التشغيل", "التأثير", "الحماية"]
        )
        self.services_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.services_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.services_table, 1)

        row = QHBoxLayout()
        btn_refresh = QPushButton("تحديث القائمة")
        btn_refresh.clicked.connect(self.refresh_services)
        row.addWidget(btn_refresh)

        btn_stop = QPushButton("إيقاف المحدد")
        btn_stop.clicked.connect(lambda: self.apply_service_changes(enable=False))
        row.addWidget(btn_stop)

        btn_start = QPushButton("تشغيل المحدد")
        btn_start.clicked.connect(lambda: self.apply_service_changes(enable=True))
        row.addWidget(btn_start)
        row.addStretch()
        layout.addLayout(row)
        self.refresh_services()
        return page

    def _tab_startup(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "برامج بدء التشغيل من الريجستري (HKCU/HKLM). التعطيل بإعادة تسمية القيمة فقط — "
            "قابل للرجوع بنقرة، وما يُحذف شي."
        ))

        self.startup_table = self._make_table(["البرنامج", "المصدر", "الأمر", "الحالة"])
        self.startup_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.startup_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.startup_table, 1)

        row = QHBoxLayout()
        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self.refresh_startup)
        row.addWidget(btn_refresh)
        btn_disable = QPushButton("تعطيل المحدد")
        btn_disable.clicked.connect(lambda: self.toggle_startup(enable=False))
        row.addWidget(btn_disable)
        btn_enable = QPushButton("إعادة تفعيل المحدد")
        btn_enable.clicked.connect(lambda: self.toggle_startup(enable=True))
        row.addWidget(btn_enable)
        row.addStretch()
        layout.addLayout(row)
        self.refresh_startup()
        return page

    def _tab_tweaks(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        power_card = Card("خطة الطاقة")
        self.power_plan_label = QLabel("—")
        power_card.add(self.power_plan_label)
        prow = QHBoxLayout()
        for label, fn in (
            ("خطة الأداء العالي", self.ctx.tweaks.set_high_performance_power_plan),
            ("خطة الأداء المطلق (مخفية)", self.ctx.tweaks.unlock_ultimate_performance),
            ("الخطة المتوازنة", self.ctx.tweaks.set_balanced_power_plan),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, f=fn, title=label: self._run_tweak(f, title))
            prow.addWidget(btn)
        prow.addStretch()
        power_card.add_layout(prow)
        layout.addWidget(power_card)

        ui_card = Card("الواجهة والاستجابة")
        urow = QGridLayout()
        self.btn_visual = QPushButton("المؤثرات البصرية → أفضل أداء")
        self.btn_visual.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.set_visual_effects_best_performance, "المؤثرات البصرية"))
        urow.addWidget(self.btn_visual, 0, 0)
        btn_transparency = QPushButton("تعطيل الشفافية")
        btn_transparency.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.disable_transparency, "الشفافية"))
        urow.addWidget(btn_transparency, 0, 1)
        btn_anim = QPushButton("تعطيل حركات النوافذ")
        btn_anim.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.disable_animations, "حركات النوافذ"))
        urow.addWidget(btn_anim, 0, 2)
        btn_menu = QPushButton("تسريع ظهور القوائم")
        btn_menu.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.set_menu_delay_fast, "تسريع القوائم"))
        urow.addWidget(btn_menu, 1, 0)
        btn_bg = QPushButton("تعطيل تطبيقات الخلفية (UWP)")
        btn_bg.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.disable_background_apps, "تطبيقات الخلفية"))
        urow.addWidget(btn_bg, 1, 1)
        btn_bg_on = QPushButton("إعادة تفعيل تطبيقات الخلفية")
        btn_bg_on.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.enable_background_apps, "تطبيقات الخلفية"))
        urow.addWidget(btn_bg_on, 1, 2)
        ui_card.add_layout(urow)
        self.tweaks_state_label = QLabel("")
        self.tweaks_state_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.tweaks_state_label.setWordWrap(True)
        ui_card.add(self.tweaks_state_label)
        layout.addWidget(ui_card)

        system_card = Card("تحسينات النظام (تتطلب صلاحيات مدير)")
        srow = QHBoxLayout()
        btn_fast = QPushButton("تفعيل الإقلاع السريع")
        btn_fast.clicked.connect(lambda: self._run_tweak(lambda: self.ctx.tweaks.set_fast_startup(True), "الإقلاع السريع"))
        srow.addWidget(btn_fast)
        btn_fast_off = QPushButton("تعطيل الإقلاع السريع")
        btn_fast_off.clicked.connect(lambda: self._run_tweak(lambda: self.ctx.tweaks.set_fast_startup(False), "الإقلاع السريع"))
        srow.addWidget(btn_fast_off)
        btn_hags = QPushButton("تفعيل جدولة GPU (HAGS)")
        btn_hags.clicked.connect(lambda: self._run_tweak(lambda: self.ctx.tweaks.set_hardware_gpu_scheduling(True), "HAGS"))
        srow.addWidget(btn_hags)
        btn_ntfs = QPushButton("تقليل كتابات القرص (NTFS)")
        btn_ntfs.clicked.connect(lambda: self._run_tweak(self.ctx.tweaks.optimize_ntfs_last_access, "NTFS"))
        srow.addWidget(btn_ntfs)
        srow.addStretch()
        system_card.add_layout(srow)
        layout.addWidget(system_card)

        advanced = QGroupBox("متقدم — يقلل الحماية مقابل الأداء (اقرأ قبل الاستخدام)")
        adv_layout = QVBoxLayout(advanced)
        adv_layout.addWidget(QLabel(
            "تعطيل Memory Integrity يقلل الحماية ضد برمجيات kernel الخبيثة (rootkits) مقابل أداء أعلى "
            "في بعض الحالات. لا يُنفَّذ إلا بتأكيد صريح، ويمكن التراجع من سجل التغييرات."
        ))
        btn_vbs = QPushButton("تعطيل Memory Integrity (بتأكيد)")
        btn_vbs.setObjectName("dangerButton")
        btn_vbs.clicked.connect(self.run_disable_memory_integrity)
        adv_layout.addWidget(btn_vbs)
        layout.addWidget(advanced)

        btn_bundle = QPushButton("⚡ تطبيق حزمة التسريع الموصى بها الآن")
        btn_bundle.setObjectName("primaryButton")
        btn_bundle.clicked.connect(self.run_recommended_bundle)
        layout.addWidget(btn_bundle)

        layout.addStretch()
        self._refresh_tweaks_state()
        return page

    def _tab_protection(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        info = QLabel(
            "الحماية ثلاث طبقات: <b>طبقة دائمة</b> (عمليات النواة والإقلاع — لا يمكن استثناؤها)، "
            "<b>طبقة افتراضية</b> (مكوّنات واجهة ويندوز وتطبيق الصور)، و<b>طبقتك الخاصة</b> "
            "(البرامج التي تضيفها هنا). أي برنامج هنا لا يُغلق أبدًا من البرنامج."
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        self.protection_stats_label = QLabel("")
        layout.addWidget(self.protection_stats_label)

        splitter = QSplitter(Qt.Horizontal)

        excl_card = Card("برامجك المستثناة (process_exclusions)")
        self.exclusions_list = QListWidget()
        excl_card.add(self.exclusions_list)
        exrow = QHBoxLayout()
        btn_add_app = QPushButton("إضافة من البرامج الجارية...")
        btn_add_app.setObjectName("primaryButton")
        btn_add_app.clicked.connect(self.add_protection_from_picker)
        exrow.addWidget(btn_add_app)
        btn_add_exe = QPushButton("إضافة ملف exe...")
        btn_add_exe.clicked.connect(self.add_exclusion_from_file)
        exrow.addWidget(btn_add_exe)
        btn_add_manual = QPushButton("إضافة اسم يدويًا")
        btn_add_manual.clicked.connect(self.add_exclusion_manual)
        exrow.addWidget(btn_add_manual)
        exrow.addStretch()
        excl_card.add_layout(exrow)
        splitter.addWidget(excl_card)

        prot_card = Card("تطبيقاتك المحمية (protected_apps)")
        self.protected_list = QListWidget()
        prot_card.add(self.protected_list)
        prow = QHBoxLayout()
        btn_remove_protected = QPushButton("إزالة المحدد من الحماية")
        btn_remove_protected.clicked.connect(self.remove_protected_app)
        prow.addWidget(btn_remove_protected)
        prow.addStretch()
        prot_card.add_layout(prow)
        splitter.addWidget(prot_card)
        layout.addWidget(splitter, 1)

        remove_row = QHBoxLayout()
        btn_remove_excl = QPushButton("إزالة المحدد من الاستثناءات")
        btn_remove_excl.clicked.connect(self.remove_exclusion)
        remove_row.addWidget(btn_remove_excl)
        remove_row.addStretch()
        layout.addLayout(remove_row)

        defender_card = Card("Windows Defender")
        defender_card.add(QLabel(
            "بعض برامج الحماية تعطي إنذارًا كاذبًا ضد أي برنامج غير موقّع مبني بـ PyInstaller. "
            "يمكنك إضافة مجلدات البرنامج لاستثناءات Defender (اختياري، ويتطلب صلاحيات مدير)."
        ))
        drow = QHBoxLayout()
        btn_def_add = QPushButton("إضافة استثناءات Defender")
        btn_def_add.clicked.connect(lambda: self._run_task(self.ctx.installer.add_defender_exclusions, "استثناءات Defender"))
        drow.addWidget(btn_def_add)
        btn_def_remove = QPushButton("إزالة استثناءات Defender")
        btn_def_remove.clicked.connect(lambda: self._run_task(self.ctx.installer.remove_defender_exclusions, "إزالة الاستثناءات"))
        drow.addWidget(btn_def_remove)
        drow.addStretch()
        defender_card.add_layout(drow)
        layout.addWidget(defender_card)

        self.refresh_protection_lists()
        return page

    def _tab_health(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        top = QHBoxLayout()
        self.health_summary_label = QLabel("جاري الفحص...")
        self.health_summary_label.setWordWrap(True)
        self.health_summary_label.setTextFormat(Qt.RichText)
        top.addWidget(self.health_summary_label, 1)
        layout.addLayout(top)

        self.crashes_table = self._make_table(["التطبيق", "نوع العطل", "الوقت", "الحدث"])
        layout.addWidget(SectionHeader("أعطال التطبيقات خلال 24 ساعة"))
        layout.addWidget(self.crashes_table, 1)

        self.disks_table = self._make_table(["القرص", "المستخدم %", "المتبقي GB", "الإجمالي GB"])
        layout.addWidget(SectionHeader("الأقراص"))
        layout.addWidget(self.disks_table)

        row = QHBoxLayout()
        btn_scan = QPushButton("فحص الآن")
        btn_scan.setObjectName("primaryButton")
        btn_scan.clicked.connect(self.run_health_scan)
        row.addWidget(btn_scan)
        btn_export = QPushButton("تصدير تقرير")
        btn_export.clicked.connect(self.export_health_report)
        row.addWidget(btn_export)
        btn_logs = QPushButton("فتح مجلد السجلات")
        btn_logs.clicked.connect(self.open_logs_folder)
        row.addWidget(btn_logs)
        row.addStretch()
        layout.addLayout(row)
        return page

    def _tab_journal(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "كل تغيير نفّذه البرنامج على النظام مسجّل هنا بقيمته السابقة، "
            "وتقدر ترجعه بزر واحد. التراجع متاح للتغييرات القابلة للعكس (خدمات، بدء تشغيل، ريجستري، خطة طاقة)."
        ))

        self.journal_table = self._make_table(["الوقت", "التغيير", "النوع", "الحالة"])
        self.journal_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.journal_table, 1)

        row = QHBoxLayout()
        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self.refresh_journal)
        row.addWidget(btn_refresh)
        btn_undo = QPushButton("↩ التراجع عن المحدد")
        btn_undo.setObjectName("primaryButton")
        btn_undo.clicked.connect(self.undo_selected_journal)
        row.addWidget(btn_undo)
        row.addStretch()
        layout.addLayout(row)
        self.refresh_journal()
        return page

    def _tab_logs(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output, 1)

        row = QHBoxLayout()
        btn_clear = QPushButton("مسح العرض")
        btn_clear.clicked.connect(self.log_output.clear)
        row.addWidget(btn_clear)
        btn_load = QPushButton("تحميل آخر السجل من الملف")
        btn_load.clicked.connect(self.load_file_log)
        row.addWidget(btn_load)
        btn_folder = QPushButton("فتح مجلد السجلات")
        btn_folder.clicked.connect(self.open_logs_folder)
        row.addWidget(btn_folder)
        row.addStretch()
        layout.addLayout(row)

        handler = UILogHandler(self.log_output)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        logger.info("بدأت جلسة جديدة للمستخدم %s.", self.current_user["username"])
        return page

    def _tab_users(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("إدارة حسابات البرنامج (محلية، مشفّرة، ولا تُرسل لأي مكان)."))

        self.users_list = QListWidget()
        layout.addWidget(self.users_list, 1)

        form_box = Card("إضافة مستخدم")
        form = QFormLayout()
        self.new_username = QLineEdit()
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        self.new_role = QComboBox()
        self.new_role.addItems(["user", "admin"])
        form.addRow("اسم المستخدم:", self.new_username)
        form.addRow("كلمة المرور:", self.new_password)
        form.addRow("الدور:", self.new_role)
        form_box.add_layout(form)

        row = QHBoxLayout()
        btn_add = QPushButton("إضافة")
        btn_add.setObjectName("primaryButton")
        btn_add.clicked.connect(self.add_user)
        row.addWidget(btn_add)
        btn_remove = QPushButton("حذف المحدد")
        btn_remove.clicked.connect(self.remove_user)
        row.addWidget(btn_remove)
        row.addStretch()
        form_box.add_layout(row)
        layout.addWidget(form_box)

        self.refresh_users()
        return page

    # ==================================================================
    # أدوات مساعدة للجداول والبطاقات
    # ==================================================================
    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.setMinimumHeight(150)
        return table

    @staticmethod
    def _set_table_rows(table: QTableWidget, rows: list[list]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    # ==================================================================
    # الربط والحالة
    # ==================================================================
    def _connect_signals(self) -> None:
        self.ctx.monitor.sample.connect(self._on_sample)
        self.ctx.health.report_ready.connect(self._on_health_report)
        self.ctx.notifications.notification_added.connect(self._on_notification)
        self.ctx.notifications.unread_changed.connect(self._on_unread_changed)

    def _on_notification(self, notification) -> None:
        if self.ctx.notifications.tray_toast_enabled() and self.tray.isVisible():
            self.tray.showMessage(
                notification.title,
                notification.message or "",
                QSystemTrayIcon.Information,
                5000,
            )
        if self.ctx.notifications.show_in_app():
            self.toasts.show_message(notification.title, notification.message, notification.level.value)

    def _on_unread_changed(self, count: int) -> None:
        self.btn_notifications.setText(f"🔔 التنبيهات ({count})")

    def _on_sample(self, snapshot: dict) -> None:
        if snapshot:
            self._refresh_dashboard(snapshot)

    def _refresh_dashboard(self, snapshot: dict | None) -> None:
        if not snapshot:
            return
        try:
            history = snapshot.get("history", {})
            self.card_cpu.update_value(
                snapshot.get("cpu_percent"),
                subtitle=f"{snapshot.get('cpu_count')} نواة — {snapshot.get('cpu_freq_mhz', 0):.0f} MHz",
                history=history.get("cpu"),
            )
            self.card_ram.update_value(
                snapshot.get("ram_percent"),
                subtitle=f"{snapshot.get('ram_used_mb'):.0f} / {snapshot.get('ram_total_mb'):.0f} MB",
                history=history.get("ram"),
            )
            self.card_disk.update_value(
                snapshot.get("disk_percent"),
                subtitle=(
                    f"متبقي {snapshot.get('disk_free_gb')} GB من {snapshot.get('disk_total_gb')} GB — "
                    f"قراءة {snapshot.get('disk_read_mb_s')} / كتابة {snapshot.get('disk_write_mb_s')} MB/s"
                ),
                history=history.get("disk"),
            )
            self._net_history.append(float(snapshot.get("net_down_kb_s", 0) or 0))
            self.card_net.sparkline.set_max(max(list(self._net_history) + [1.0]))
            self.card_net.update_value(
                None,
                text=f"{snapshot.get('net_down_kb_s', 0):.0f} KB/s",
                subtitle=f"رفع {snapshot.get('net_up_kb_s', 0):.0f} KB/s — {snapshot.get('process_count')} عملية",
                history=list(self._net_history),
            )

            if self.tabs.currentIndex() == 0:
                rows = [
                    [p["name"], p["pid"], p["cpu_percent"], p["memory_mb"], "✔" if p.get("protected") else ""]
                    for p in snapshot.get("top_processes", [])
                ]
                self._set_table_rows(self.dash_procs, rows)
        except Exception as exc:
            logger.debug("Dashboard refresh failed: %s", exc)

        self.sys_info_label.setText(self._system_info_html())

    def _system_info_html(self) -> str:
        try:
            from src.utils.winapi import get_windows_info

            info = get_windows_info()
            uptime = int((self.ctx.monitor.last_sample or {}).get("uptime_seconds", 0))
            hours, remainder = divmod(uptime, 3600)
            minutes = remainder // 60
            drives = "</li><li>".join(
                f"{os.path.splitdrive(p)[0] or p} — متبقي {human_size(psutil_free(p))}"
                for p in _safe_mounts()
            )
            return (
                f"<b>{info.get('name')}</b> {info.get('version')} (بناء {info.get('build')}) — "
                f"{info.get('architecture')}<br>"
                f"مدة التشغيل: {hours} ساعة و{minutes} دقيقة<br>"
                f"الأقراص:<ul><li>{drives}</li></ul>"
            )
        except Exception:
            return "تعذر قراءة معلومات النظام."

    def _update_badges(self) -> None:
        if is_admin():
            self.admin_badge.setText("🛡 مدير")
            self.admin_badge.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.admin_badge.setText("⚠ بدون صلاحيات مدير")
            self.admin_badge.setStyleSheet(f"color: {COLORS['warning']};")
        test_mode = bool(self.ctx.settings.get("test_mode"))
        self.test_badge.setText("🧪 وضع المعاينة مفعّل" if test_mode else "")
        self.test_badge.setStyleSheet(f"color: {COLORS['warning']};")

    def refresh_badges(self) -> None:
        self._update_badges()

    # ==================================================================
    # إدارة المهام (خيوط)
    # ==================================================================
    def _run_task(self, fn, label: str, on_success=None, **kwargs):
        """تشغيل مهمة في خيط منفصل مع تعطيل العرض وحفظ النتيجة."""
        self._tasks += 1
        self.busy_label.setText(f"⏳ {label}...")

        def _done(result):
            self._tasks = max(0, self._tasks - 1)
            if self._tasks == 0:
                self.busy_label.setText("")
            self._handle_result(result)

        def _error(message: str):
            self._tasks = max(0, self._tasks - 1)
            if self._tasks == 0:
                self.busy_label.setText("")
            self.ctx.notifications.error(f"فشل: {label}", message, source="task")
            self.last_result_label.setText(f"آخر نتيجة: فشل في {label}")

        self.last_result_label.setText(f"آخر نتيجة: جاري {label}...")
        self.ctx.tasks.run(fn, on_success=_done, on_error=_error, label=label, **kwargs)

    def _handle_result(self, result) -> None:
        if isinstance(result, ActionResult):
            if result.success:
                self.ctx.notifications.success(result.message.split(".")[0], result.message, source="task")
            else:
                self.ctx.notifications.warning(result.message.split(".")[0], result.message, source="task")
            self.last_result_label.setText(f"آخر نتيجة: {result.message[:90]}")
        elif isinstance(result, list):
            for _label, sub in result:
                self._handle_result(sub)
        else:
            logger.info("نتيجة: %s", result)
            self.last_result_label.setText(f"آخر نتيجة: {str(result)[:90]}")

    def _run_tweak(self, fn, label: str) -> None:
        self._run_task(fn, label)

    # ==================================================================
    # التنظيف
    # ==================================================================
    def run_estimate_temp(self) -> None:
        self.temp_size_label.setText("جاري حساب الحجم...")
        include = self.cb_user_temp.isChecked()

        def _show(size: int):
            self.temp_size_label.setText(f"حجم المخلفات المؤقتة الحالي: <b>{human_size(size)}</b>")
            self.last_result_label.setText("آخر نتيجة: حساب حجم الملفات المؤقتة")

        self.ctx.tasks.run(
            self.ctx.cleaner.estimate_temp_size, on_success=_show,
            on_error=lambda err: self.temp_size_label.setText(f"تعذر الحساب: {err}"),
            label="حساب الحجم", include_temp=include,
        )

    def run_clean_temp(self, silent: bool = False) -> None:
        include = self.cb_user_temp.isChecked()
        if include and not silent:
            dialog = ConfirmDialog(
                "تنظيف مجلد المستخدم المؤقت",
                "سيتم حذف ملفات %TEMP% الخاصة بحسابك. أي برنامج مفتوح يستخدم ملفًا مؤقتًا لن يتأثر "
                "(الملفات المقفلة تُتخطى تلقائيًا)، لكن يُفضل حفظ عملك أولًا.",
                bullets=["تُحذف الملفات المؤقتة لويندوز دائمًا.", "مجلد %TEMP% يُضمَّن الآن بطلبك."],
                confirm_text="تنظيف",
                parent=self,
            )
            if dialog.exec() != ConfirmDialog.Accepted:
                return

        def _done(result: ActionResult):
            if result.data.get("freed"):
                result.message += f" (المساحة المحرّرة: {human_size(result.data['freed'])})"
            self._handle_result(result)

        self.ctx.tasks.run(self.ctx.cleaner.clean_temp_files, on_success=_done,
                           on_error=self._task_error, label="تنظيف الملفات المؤقتة", include_temp=include)

    def run_empty_recycle_bin(self) -> None:
        dialog = ConfirmDialog(
            "إفراغ سلة المحذوفات",
            "سيتم حذف كل ما في سلة المحذوفات نهائيًا لكل الأقراص. لا يمكن التراجع عن هذه العملية.",
            confirm_text="إفراغ السلة",
            parent=self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self.ctx.tasks.run(self.ctx.cleaner.clean_recycle_bin, on_success=self._handle_result,
                           on_error=self._task_error, label="إفراغ سلة المحذوفات")

    def run_recycle_size(self) -> None:
        from src.utils.winapi import recycle_bin_size

        size, items = recycle_bin_size()
        self.recycle_label.setText(f"حجم السلة: <b>{human_size(size)}</b> في {items} عنصرًا.")
        self.last_result_label.setText("آخر نتيجة: قراءة حجم سلة المحذوفات")

    def run_clean_updates(self) -> None:
        dialog = ConfirmDialog(
            "تفريغ مخلفات التحديثات",
            "سيتم إيقاف خدمات التحديث مؤقتًا، حذف ملفات التحديثات القديمة، ثم إعادة تشغيل الخدمات تلقائيًا. "
            "لا يحذف هذا التحديثات المثبّتة.",
            confirm_text="تفريغ",
            parent=self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self.ctx.tasks.run(self.ctx.cleaner.clean_old_updates, on_success=self._handle_result,
                           on_error=self._task_error, label="تنظيف مخلفات التحديثات")

    def run_clean_reports(self) -> None:
        self.ctx.tasks.run(self.ctx.cleaner.clean_error_reports, on_success=self._handle_result,
                           on_error=self._task_error, label="تنظيف تقارير الأعطال")

    def pick_browser_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "اختر مجلد بيانات المتصفح (مثال: ...\\Local\\Google\\Chrome\\User Data)",
            os.path.expanduser("~"),
        )
        if not folder:
            return
        self._browser_folder = folder
        self.browser_path_label.setText(f"المجلد المحدد: {folder}")

    def run_clean_browser_cache(self) -> None:
        folder = getattr(self, "_browser_folder", "")
        if not folder:
            QMessageBox.information(self, "تنبيه", "اختر مجلد بيانات المتصفح أولًا.")
            return
        self.ctx.tasks.run(
            self.ctx.cleaner.clean_browser_cache, on_success=self._handle_result,
            on_error=self._task_error, label="تنظيف كاش المتصفح", browser_local_appdata_folder=folder,
        )

    # ==================================================================
    # العمليات
    # ==================================================================
    def refresh_process_table(self) -> None:
        self.ctx.tasks.run(
            self.ctx.optimizer.list_high_resource_processes, on_success=self._show_processes_table,
            on_error=self._task_error, label="قراءة العمليات", top_n=50,
        )

    def _show_processes_table(self, processes: list[dict]) -> None:
        rows = [
            [p["name"], p["pid"], p["cpu_percent"], p["memory_mb"],
             p.get("protection_reason") or ("✔ محمية" if p.get("protected") else "")]
            for p in processes
        ]
        self._set_table_rows(self.procs_table, rows)
        self._update_protection_summary()

    def _selected_process(self) -> dict | None:
        row = self.procs_table.currentRow()
        if row < 0:
            return None
        name_item = self.procs_table.item(row, 0)
        pid_item = self.procs_table.item(row, 1)
        return {"name": name_item.text() if name_item else "", "pid": int(pid_item.text()) if pid_item else 0}

    def run_kill_selected_process(self) -> None:
        target = self._selected_process()
        if not target:
            QMessageBox.information(self, "تنبيه", "حدد عملية من الجدول أولًا.")
            return
        allowed, reason = self.ctx.protection.check_process(name=target["name"], pid=target["pid"])
        if not allowed:
            QMessageBox.warning(self, "محمية", f"لا يمكن إنهاء {target['name']}: {reason}.")
            return
        dialog = ConfirmDialog(
            "إنهاء عملية",
            f"سيتم إنهاء {target['name']} (PID {target['pid']}). أي عمل غير محفوظ في هذا البرنامج سيُفقد.",
            confirm_text="إنهاء",
            parent=self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self.ctx.tasks.run(
            self._terminate_by_pid, on_success=self._handle_result, on_error=self._task_error,
            label=f"إنهاء {target['name']}", pid=target["pid"], name=target["name"],
        )

    def _terminate_by_pid(self, pid: int, name: str = "") -> ActionResult:
        import psutil

        try:
            proc = psutil.Process(pid)
            allowed, reason = self.ctx.protection.check_process(proc, name=name or proc.name(), pid=pid)
            if not allowed:
                return ActionResult(False, f"العملية محمية: {reason}.")
            self.ctx.optimizer.terminate_process(proc, name or proc.name())
            return ActionResult(True, f"تم إنهاء {name or proc.name()} (PID {pid}).")
        except Exception as exc:
            return ActionResult(False, f"تعذر إنهاء العملية: {exc}")

    def run_kill_force_list(self) -> None:
        self.ctx.tasks.run(self.ctx.optimizer.kill_unwanted_processes, on_success=self._handle_result,
                           on_error=self._task_error, label="إنهاء قائمة الإنهاء")

    def run_kill_all_except_excluded(self) -> None:
        summary = self.ctx.protection.summary()
        dialog = ConfirmDialog(
            "تحذير: إنهاء كل العمليات غير المستثناة",
            "سيتم إنهاء كل عملية جارية على الجهاز ما عدا برامجك المستثناة والمحمية. "
            "أي عمل غير محفوظ في البرامج المفتوحة سيُفقد.",
            bullets=[
                f"عمليات محمية دائمًا (نواة/إقلاع ويندوز): {summary['hard_protected_count']}.",
                f"استثناءاتك الحالية: {summary['exclusions_count']} اسم.",
                f"تطبيقات أضفتها للحماية: {summary['protected_apps_count']}.",
                "البرنامج نفسه وكل عملية يشغّلها محمية تلقائيًا.",
            ],
            require_checkbox=True,
            checkbox_text="أفهم أن البرامج غير المستثناة ستُغلق الآن",
            confirm_text="تنفيذ الإنهاء",
            parent=self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self.ctx.tasks.run(self.ctx.optimizer.kill_all_except_excluded, on_success=self._kill_all_done,
                           on_error=self._task_error, label="إنهاء العمليات غير المستثناة")

    def _kill_all_done(self, result: ActionResult) -> None:
        data = result.data or {}
        killed = data.get("killed") or []
        protected = data.get("protected") or []
        names = ", ".join(sorted({k.get("name", "") for k in killed if isinstance(k, dict)}))[:300]
        message = f"أُنهيت {len(killed)} عملية. حُميت {len(protected)} عملية."
        if names:
            message += f"\n\nالعمليات المُنهية: {names}"
        self._handle_result(ActionResult(True, message, details=result.details))
        self.refresh_process_table()

    def _update_protection_summary(self) -> None:
        summary = self.ctx.protection.summary()
        self.protection_summary_label.setText(
            f"محمية دائمًا: {summary['hard_protected_count']} عملية | "
            f"مستثنياتك: {summary['exclusions_count']} | "
            f"تطبيقاتك المحمية: {summary['protected_apps_count']} | "
            "أي عملية غير ذلك قابلة للإنهاء من زر الإنهاء الجماعي."
        )

    # ==================================================================
    # الحماية والاستثناءات
    # ==================================================================
    def refresh_protection_lists(self) -> None:
        self.exclusions_list.clear()
        for name in sorted(self.ctx.settings.get("process_exclusions") or [], key=str.lower):
            self.exclusions_list.addItem(name)
        self.protected_list.clear()
        for name in sorted(self.ctx.settings.get("protected_apps") or [], key=str.lower):
            self.protected_list.addItem(name)
        summary = self.ctx.protection.summary()
        self.protection_stats_label.setText(
            f"محمية دائمًا: <b>{summary['hard_protected_count']}</b> عملية نواة/إقلاع | "
            f"استثناءاتك: <b>{summary['exclusions_count']}</b> | "
            f"تطبيقاتك المحمية: <b>{summary['protected_apps_count']}</b> | "
            f"خدمات محمية: <b>{summary['hard_protected_services_count']}</b>"
        )
        self._update_protection_summary()

    def add_protection_from_picker(self) -> None:
        dialog = ProtectionPickerDialog(self.ctx.protection, self)
        if dialog.exec() != ProtectionPickerDialog.Accepted:
            return
        added = []
        for name in dialog.selected:
            if self.ctx.protection.add_app_to_protection(name):
                added.append(name)
        if added:
            self.ctx.notifications.success("تمت الحماية", f"أُضيف {len(added)} برنامجًا: " + ", ".join(added[:8]))
            self.refresh_protection_lists()
        else:
            self.ctx.notifications.warning("لم يُضف شيء", "لم يتم تحديد أي برنامج جديد.")

    def add_exclusion_from_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "اختر ملف البرنامج", os.path.expanduser("~"), "ملفات تنفيذية (*.exe);;كل الملفات (*)"
        )
        if not path:
            return
        name = os.path.basename(path)
        if self.ctx.settings.add_process_exclusion(name):
            self.ctx.notifications.success("استثناء جديد", f"أُضيف {name} إلى قائمة الاستثناءات.")
            self.refresh_protection_lists()

    def add_exclusion_manual(self) -> None:
        name, ok = QInputDialog.getText(self, "استثناء يدوي", "اسم العملية (مثال: myapp.exe):")
        if ok and name.strip():
            if self.ctx.settings.add_process_exclusion(name.strip()):
                self.ctx.notifications.success("استثناء جديد", f"أُضيف {name.strip()}.")
                self.refresh_protection_lists()

    def remove_exclusion(self) -> None:
        item = self.exclusions_list.currentItem()
        if item is None:
            return
        name = item.text()
        protected = {x.lower() for x in (self.ctx.settings.get("protected_apps") or [])}
        if name.lower() in protected:
            self.ctx.notifications.warning("محمي", "هذا البرنامج في قائمة الحماية — أزله من قائمة الحماية أولًا.")
            return
        if self.ctx.settings.remove_process_exclusion(name):
            self.ctx.notifications.info("حُذف استثناء", f"{name} أُزيل من الاستثناءات.")
            self.refresh_protection_lists()

    def remove_protected_app(self) -> None:
        item = self.protected_list.currentItem()
        if item is None:
            return
        name = item.text()
        if self.ctx.protection.remove_app_from_protection(name):
            self.ctx.notifications.info("أُزيلت الحماية", f"{name} لم يعد محميًا.")
            self.refresh_protection_lists()

    # ==================================================================
    # الخدمات وبدء التشغيل
    # ==================================================================
    def refresh_services(self) -> None:
        self.ctx.tasks.run(self.ctx.optimizer.list_services_status, on_success=self._show_services,
                           on_error=self._task_error, label="قراءة الخدمات")

    def _show_services(self, services: list[dict]) -> None:
        rows = []
        for svc in services:
            status = "▶ تعمل" if svc.get("status") == "running" else "⏸ متوقفة"
            rows.append([
                svc["name"], status, svc.get("start_type", "?"), svc.get("description", ""),
                svc.get("protection_reason", "") if svc.get("protected") else "",
            ])
        self._set_table_rows(self.services_table, rows)

    def apply_service_changes(self, enable: bool) -> None:
        rows = sorted({index.row() for index in self.services_table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "تنبيه", "حدد خدمة واحدة على الأقل من الجدول.")
            return
        names = [self.services_table.item(row, 0).text() for row in rows]
        action = "تشغيل" if enable else "إيقاف"
        dialog = ConfirmDialog(
            f"{action} الخدمات المحددة",
            f"سيتم {action} الخدمات: {', '.join(names)}.\nكل تغيير قابل للتراجع من سجل التغييرات.",
            confirm_text=action,
            parent=self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return

        def _run_all():
            results = [self.ctx.optimizer.set_service_state(name, enable) for name in names]
            ok = sum(1 for r in results if r.success)
            return ActionResult(ok > 0, f"انتهت العملية: نجح {ok} من {len(results)} خدمات.",
                                details="\n".join(r.message for r in results))

        self.ctx.tasks.run(_run_all, on_success=self._after_service_change, on_error=self._task_error,
                           label=f"{action} الخدمات")

    def _after_service_change(self, result: ActionResult) -> None:
        self._handle_result(result)
        self.refresh_services()

    def refresh_startup(self) -> None:
        self.ctx.tasks.run(self.ctx.optimizer.list_startup_items, on_success=self._show_startup,
                           on_error=self._task_error, label="قراءة برامج بدء التشغيل")

    def _show_startup(self, items: list[dict]) -> None:
        rows = [
            [item["original_name"], item["hive"], item["command"],
             "⛔ معطّل" if item["disabled"] else "✅ مفعّل"]
            for item in items
        ]
        self._set_table_rows(self.startup_table, rows)
        for index, item in enumerate(items):
            cell = self.startup_table.item(index, 0)
            if cell:
                cell.setData(Qt.UserRole, item)

    def toggle_startup(self, enable: bool) -> None:
        rows = sorted({index.row() for index in self.startup_table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "تنبيه", "حدد برنامجًا واحدًا على الأقل.")
            return

        def _run_all():
            ok = 0
            messages = []
            for row in rows:
                data = self.startup_table.item(row, 0).data(Qt.UserRole) or {}
                name = data.get("name")
                hive = data.get("hive", "HKCU")
                disabled = data.get("disabled", False)
                if enable and not disabled:
                    continue
                if not enable and disabled:
                    continue
                result = self.ctx.optimizer.set_startup_item_enabled(name, hive, enabled=enable)
                ok += 1 if result.success else 0
                messages.append(result.message)
            return ActionResult(ok > 0, f"تغيّر {ok} عنصرًا.", details="\n".join(messages))

        self.ctx.tasks.run(_run_all, on_success=self._after_startup_change, on_error=self._task_error,
                           label="تعديل برامج بدء التشغيل")

    def _after_startup_change(self, result: ActionResult) -> None:
        self._handle_result(result)
        self.refresh_startup()
        self.refresh_journal()

    # ==================================================================
    # تسريع النظام والصحة
    # ==================================================================
    def run_recommended_bundle(self) -> None:
        self.ctx.tasks.run(self.ctx.tweaks.apply_recommended_bundle, on_success=self._bundle_done,
                           on_error=self._task_error, label="حزمة التسريع")

    def _bundle_done(self, results) -> None:
        ok = sum(1 for _label, result in results if result.success)
        self.ctx.notifications.success("حزمة التسريع", f"اكتملت: نجح {ok} من {len(results)} خطوات.")
        for label, result in results:
            logger.info("[%s] %s", label, result.message)
        self._refresh_tweaks_state()
        self.refresh_journal()

    def _refresh_tweaks_state(self) -> None:
        state = self.ctx.tweaks.current_state()
        if not state.get("available"):
            self.tweaks_state_label.setText("الريجستري غير متوفر — بعض التحسينات تحتاج ويندوز.")
            self.power_plan_label.setText("—")
            return
        self.power_plan_label.setText(f"خطة الطاقة الحالية: <b>{state.get('power_plan', '—')}</b>")
        parts = [
            "المؤثرات البصرية مضبوطة للأداء" if state.get("visual_effects_best_performance") else "المؤثرات البصرية: افتراضية",
            "تطبيقات الخلفية معطّلة" if state.get("background_apps_disabled") else "تطبيقات الخلفية: مفعّلة",
            "حركات النوافذ معطّلة" if state.get("animations_disabled") else "حركات النوافذ: مفعّلة",
            "الإقلاع السريع مفعّل" if state.get("fast_startup") else "الإقلاع السريع: معطّل",
            "HAGS مفعّل" if state.get("hags") else "HAGS: معطّل",
        ]
        self.tweaks_state_label.setText(" | ".join(parts))

    def run_disable_memory_integrity(self) -> None:
        dialog = ConfirmDialog(
            "تأكيد مطلوب: Memory Integrity",
            "تعطيل Memory Integrity يقلل الحماية ضد برمجيات خبيثة على مستوى kernel (rootkits) "
            "مقابل أداء أعلى في بعض الحالات. لا يُنفَّذ إلا بموافقتك الصريحة.",
            require_checkbox=True,
            checkbox_text="أفهم المقايضة الأمنية وأريد التعطيل",
            confirm_text="تعطيل",
            parent=self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self._run_tweak(lambda: self.ctx.tweaks.toggle_memory_integrity(False, confirm=True), "Memory Integrity")

    def run_health_scan(self) -> None:
        self.ctx.tasks.run(self.ctx.health.collect_report, on_success=self._on_health_report,
                           on_error=self._task_error, label="فحص صحة النظام")

    def _on_health_report(self, report: dict) -> None:
        if not report:
            return
        win = report.get("windows", {})
        self.health_summary_label.setText(
            f"<b>{win.get('name', '?')}</b> {win.get('version', '')} (بناء {win.get('build', '?')}) — "
            f"مدة التشغيل {report.get('uptime_hours', '?')} ساعة<br>"
            f"أخطاء النظام خلال 24 ساعة: <b>{report.get('system_errors_24h', 0)}</b> | "
            f"أعطال التطبيقات المكتشفة: <b>{len(report.get('recent_crashes', []))}</b>"
        )
        rows = [
            [crash.get("app"), crash.get("kind"), crash.get("timestamp"), crash.get("event_id")]
            for crash in report.get("recent_crashes", [])
        ]
        self._set_table_rows(self.crashes_table, rows)
        disk_rows = [
            [disk.get("mount"), disk.get("percent"), disk.get("free_gb"), disk.get("total_gb")]
            for disk in report.get("disks", [])
        ]
        self._set_table_rows(self.disks_table, disk_rows)

    def export_health_report(self) -> None:
        report = self.ctx.health.last_report or self.ctx.health.collect_report()
        text = self.ctx.health.summarize(report)
        TextReportDialog("تقرير صحة النظام", text, self).exec()

    # ==================================================================
    # سجل التغييرات والسجلات
    # ==================================================================
    def refresh_journal(self) -> None:
        entries = self.ctx.journal.latest(200)
        rows = []
        for entry in entries:
            status = "↩ رُجّع" if entry.get("undone") else ("قابل للتراجع" if self.ctx.journal.can_undo(entry) else "غير قابل")
            rows.append([entry.get("time", ""), entry.get("description", ""), entry.get("kind", ""), status])
        self._set_table_rows(self.journal_table, rows)
        for index, entry in enumerate(entries):
            cell = self.journal_table.item(index, 0)
            if cell:
                cell.setData(Qt.UserRole, entry.get("id"))

    def undo_selected_journal(self) -> None:
        row = self.journal_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "تنبيه", "حدد تغييرًا من الجدول.")
            return
        entry_id = self.journal_table.item(row, 0).data(Qt.UserRole)
        ok, message = self.ctx.journal.undo(int(entry_id))
        if ok:
            self.ctx.notifications.success("تراجع", message)
        else:
            self.ctx.notifications.warning("لم يتم التراجع", message)
        self.refresh_journal()

    def load_file_log(self) -> None:
        text = read_log_tail(300)
        self.log_output.setPlainText(text or "لا يوجد ملف سجل بعد.")

    def open_logs_folder(self) -> None:
        folder = logs_dir()
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                os.system(f'xdg-open "{folder}" >/dev/null 2>&1 &')
        except Exception as exc:
            QMessageBox.information(self, "السجلات", f"مجلد السجلات: {folder}\n({exc})")

    # ==================================================================
    # المستخدمون
    # ==================================================================
    def refresh_users(self) -> None:
        self.users_list.clear()
        for user in self.ctx.auth.list_users():
            self.users_list.addItem(
                f"{user.get('username')} — {'مدير' if user.get('role') == 'admin' else 'مستخدم'}"
            )

    def add_user(self) -> None:
        username = self.new_username.text().strip()
        password = self.new_password.text()
        role = self.new_role.currentText()
        try:
            self.ctx.auth.create_user(username, password, role=role)
        except Exception as exc:
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self.new_username.clear()
        self.new_password.clear()
        self.ctx.notifications.success("مستخدم جديد", f"أُنشئ الحساب {username} ({role}).")
        self.refresh_users()

    def remove_user(self) -> None:
        item = self.users_list.currentItem()
        if item is None:
            return
        username = item.text().split(" — ")[0]
        if username == self.current_user.get("username"):
            QMessageBox.warning(self, "غير مسموح", "لا يمكنك حذف الحساب الذي تستخدمه الآن.")
            return
        dialog = ConfirmDialog("حذف مستخدم", f"سيتم حذف الحساب {username} نهائيًا.", confirm_text="حذف", parent=self)
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        if self.ctx.auth.delete_user(username):
            self.ctx.notifications.info("حذف مستخدم", f"حُذف الحساب {username}.")
            self.refresh_users()
        else:
            QMessageBox.warning(self, "تعذر الحذف", "لا يمكن حذف آخر حساب مدير في البرنامج.")

    # ==================================================================
    # الإعدادات والتوثيق والتنبيهات
    # ==================================================================
    def open_settings(self) -> None:
        dialog = SettingsWindow(self.ctx, self)
        if dialog.exec() == SettingsWindow.Accepted:
            self._update_badges()
            self._refresh_tweaks_state()
            self.refresh_protection_lists()

    def open_notifications(self) -> None:
        dialog = NotificationsCenterDialog(self.ctx.notifications, self)
        dialog.exec()
        self.ctx.notifications.mark_all_read()

    def open_docs(self) -> None:
        import webbrowser

        docs_path = resource_path("docs/docs.html")
        try:
            webbrowser.open(f"file:///{docs_path.replace(os.sep, '/')}")
        except Exception as exc:
            QMessageBox.information(self, "التوثيق", f"افتح الملف يدويًا: {docs_path}\n({exc})")

    def logout(self) -> None:
        self.logged_out = True
        self.ctx.stop_background_services()
        self._quit_tray()
        self.close()

    def _quit_tray(self) -> None:
        try:
            if self.tray is not None:
                self.tray.hide()
        except Exception:
            pass

    def _task_error(self, message: str) -> None:
        self.ctx.notifications.error("فشلت العملية", message, source="task")
        self.last_result_label.setText(f"آخر نتيجة: فشل — {message[:80]}")

    # ==================================================================
    # أيقونة شريط المهام
    # ==================================================================
    def _build_tray(self) -> None:
        icon = load_app_icon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(f"{APP_NAME} {APP_VERSION}")
        menu = QMenu()

        action_show = QAction("فتح النافذة", self)
        action_show.triggered.connect(self.show_normal)
        menu.addAction(action_show)

        action_bundle = QAction("⚡ تسريع سريع", self)
        action_bundle.triggered.connect(self.run_recommended_bundle)
        menu.addAction(action_bundle)

        action_clean = QAction("🧹 تنظيف الملفات المؤقتة", self)
        action_clean.triggered.connect(lambda: self.run_clean_temp(silent=True))
        menu.addAction(action_clean)

        action_scan = QAction("🩺 فحص الصحة", self)
        action_scan.triggered.connect(self.run_health_scan)
        menu.addAction(action_scan)

        menu.addSeparator()
        self.action_notifications = QAction("الإشعارات", self, checkable=True)
        self.action_notifications.setChecked(self.ctx.notifications.tray_toast_enabled())
        self.action_notifications.toggled.connect(self._toggle_tray_toast)
        menu.addAction(self.action_notifications)

        menu.addSeparator()
        action_quit = QAction("خروج", self)
        action_quit.triggered.connect(self.quit_app)
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _toggle_tray_toast(self, enabled: bool) -> None:
        notifications = dict(self.ctx.settings.get("notifications") or {})
        notifications["tray_toast"] = bool(enabled)
        self.ctx.settings.set("notifications", notifications)

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_normal()

    def show_normal(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()
        self.raise_()

    def quit_app(self) -> None:
        self.logged_out = False
        self.close()
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    # ==================================================================
    # أحداث النافذة
    # ==================================================================
    def closeEvent(self, event) -> None:  # noqa: N802
        minimize_setting = bool((self.ctx.settings.get("startup") or {}).get("minimize_to_tray_on_close", True))
        if not self.logged_out and minimize_setting and self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self._tray_notice_shown = True
                self.tray.showMessage(
                    APP_NAME,
                    "البرنامج يعمل في الخلفية. اضغط مرتين على الأيقونة لفتحه، أو اختر خروج من القائمة.",
                    QSystemTrayIcon.Information,
                    6000,
                )
            return

        self.ctx.stop_background_services()
        self.ctx.tasks.wait_all(3000)
        self._quit_tray()
        super().closeEvent(event)


def _safe_mounts():
    """نقاط تحميل الأقراص المتاحة (بدون رمي استثناء)."""
    import psutil

    mounts = []
    try:
        for part in psutil.disk_partitions(all=False):
            if part.mountpoint not in mounts:
                mounts.append(part.mountpoint)
    except Exception:
        pass
    return mounts


def psutil_free(mount: str) -> int:
    import psutil

    try:
        return psutil.disk_usage(mount).free
    except Exception:
        return 0


__all__ = ["MainWindow", "load_app_icon"]
