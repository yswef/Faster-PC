"""
سياق التطبيق (AppContext) — نقطة تجميع واحدة لكل خدمات البرنامج.

الفائدة: الواجهة لا تُنشئ الموديولات بنفسها ولا تعرف تفاصيلها؛ تستقبل سياقًا
جاهزًا وتتعامل معه. هذا يجعل تشغيل الاختبارات ممكنًا بدون واجهة (Headless)،
ويمنع الاستيرادات الدائرية بين النوافذ والموديولات.
"""

from __future__ import annotations

import logging

from src.config.settings import SettingsManager
from src.core.cleaner import SystemCleaner
from src.core.exclusions import ProtectionManager
from src.core.health import HealthMonitor
from src.core.installer import SystemInstaller
from src.core.journal import ChangeJournal
from src.core.monitor import PerformanceMonitor
from src.core.notifications import NotificationCenter
from src.core.optimizer import SystemOptimizer
from src.core.repair import SystemRepair
from src.core.tweaks import PerformanceTweaks
from src.utils.auth import AuthManager
from src.utils.paths import journal_path
from src.utils.winapi import is_admin
from src.utils.workers import TaskManager

logger = logging.getLogger(__name__)


class AppContext:
    """حاوية الخدمات المشتركة بين كل نوافذ البرنامج."""

    def __init__(self, settings: SettingsManager | None = None):
        self.settings = settings or SettingsManager()
        self.journal = ChangeJournal(journal_path())
        self.notifications = NotificationCenter(self.settings)
        self.protection = ProtectionManager(self.settings)
        self.cleaner = SystemCleaner(self.settings, notifier=self.notifications)
        self.optimizer = SystemOptimizer(
            self.settings, journal=self.journal, notifier=self.notifications
        )
        self.tweaks = PerformanceTweaks(self.settings, journal=self.journal, notifier=self.notifications)
        self.repair = SystemRepair(self.settings, notifier=self.notifications)
        self.monitor = PerformanceMonitor(self.settings)
        self.health = HealthMonitor(self.settings)
        self.installer = SystemInstaller(self.settings, notifier=self.notifications)
        self.auth = AuthManager(self.settings)
        self.tasks = TaskManager()
        self.current_user: dict = {}

        self._wire_notifications()

    # ------------------------------------------------------------------
    def _wire_notifications(self) -> None:
        """تحويل أحداث المراقبة إلى تنبيهات مفهومة للمستخدم."""
        self.monitor.threshold_exceeded.connect(self._on_threshold)
        self.health.issue_found.connect(self._on_health_issue)

    def _on_threshold(self, metric: str, value: float) -> None:
        labels = {"cpu": "المعالج", "ram": "الذاكرة", "disk": "القرص"}
        label = labels.get(metric, metric)
        self.notifications.warning(
            f"استهلاك {label} مرتفع",
            f"استمر استهلاك {label} عند {value:.0f}% لمدة كافية — افتح تبويب الأداء لمعرفة السبب.",
            source="monitor",
        )

    def _on_health_issue(self, issue: dict) -> None:
        self.notifications.warning(
            issue.get("title", "مشكلة في النظام"),
            issue.get("detail", ""),
            source="health",
        )

    # ------------------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return is_admin()

    def start_background_services(self) -> None:
        """تشغيل المراقبة وصحة النظام (يُستدعى بعد ظهور النافذة الرئيسية)."""
        self.monitor.start()
        self.health.start()
        logger.info("Background services started (monitor + health).")

    def stop_background_services(self) -> None:
        self.monitor.stop()
        self.health.stop()

    def reload_settings(self) -> None:
        """إعادة تحميل الإعدادات من القرص وإعادة ضبط الخدمات المرتبطة بها."""
        self.settings.settings = self.settings.load()
        self.monitor.apply_settings()
        self.health.apply_settings()


__all__ = ["AppContext"]
