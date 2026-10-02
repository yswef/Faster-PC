"""
مركز التنبيهات — كل تنبيهات البرنامج تمر من هنا.

- الواجهة تعرض التنبيهات في مركز تنبيهات (مع عدّاد غير المقروء).
- أيقونة النظام تعرض Toast اختياريًا.
- التاريخ النصي محفوظ آخر 200 تنبيه (بالذاكرة + ملف state عند الطلب).
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from enum import Enum

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class Level(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Notification:
    __slots__ = ("title", "message", "level", "timestamp", "read", "source")

    def __init__(self, title: str, message: str = "", level: Level = Level.INFO, source: str = "app"):
        self.title = title
        self.message = message
        self.level = level
        self.source = source
        self.timestamp = datetime.now()
        self.read = False

    @property
    def time_text(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "message": self.message,
            "level": self.level.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"Notification({self.level.value}, {self.title!r})"


class NotificationCenter(QObject):
    """
    signal notification_added(Notification) — أي واجهة (مركز التنبيهات، أيقونة
    النظام، الشريط السفلي) تتصل به وتعرض ما يهمها.
    """

    notification_added = Signal(object)
    unread_changed = Signal(int)
    cleared = Signal()

    def __init__(self, settings_manager=None, max_history: int = 200, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self._history: deque[Notification] = deque(maxlen=max_history)
        self._unread = 0

    # ------------------------------------------------------------------
    def notify(self, title: str, message: str = "", level: Level = Level.INFO, source: str = "app") -> Notification:
        if self.settings is not None and not self._enabled():
            # حتى مع إيقاف الإشعارات، الأخطاء الحرجة لا تُكتم أبدًا.
            if level != Level.ERROR:
                logger.debug("Notification suppressed (disabled): %s", title)
                return Notification(title, message, level, source)

        notification = Notification(title, message, level, source)
        self._history.append(notification)
        self._unread += 1
        self.unread_changed.emit(self._unread)

        log_fn = {
            Level.INFO: logger.info,
            Level.SUCCESS: logger.success if hasattr(logger, "success") else logger.info,
            Level.WARNING: logger.warning,
            Level.ERROR: logger.error,
        }[level]
        log_fn("%s %s", title, f"— {message}" if message else "")
        self.notification_added.emit(notification)
        return notification

    def info(self, title: str, message: str = "", source: str = "app") -> Notification:
        return self.notify(title, message, Level.INFO, source)

    def success(self, title: str, message: str = "", source: str = "app") -> Notification:
        return self.notify(title, message, Level.SUCCESS, source)

    def warning(self, title: str, message: str = "", source: str = "app") -> Notification:
        return self.notify(title, message, Level.WARNING, source)

    def error(self, title: str, message: str = "", source: str = "app") -> Notification:
        return self.notify(title, message, Level.ERROR, source)

    # ------------------------------------------------------------------
    def history(self) -> list[Notification]:
        return list(self._history)

    def unread_count(self) -> int:
        return self._unread

    def mark_all_read(self) -> None:
        for item in self._history:
            item.read = True
        if self._unread:
            self._unread = 0
            self.unread_changed.emit(0)

    def clear(self) -> None:
        self._history.clear()
        self._unread = 0
        self.unread_changed.emit(0)
        self.cleared.emit()

    # ------------------------------------------------------------------
    def _enabled(self) -> bool:
        if self.settings is None:
            return True
        section = self.settings.get("notifications")
        if isinstance(section, dict):
            return bool(section.get("enabled", True))
        return True

    def show_in_app(self) -> bool:
        if self.settings is None:
            return True
        section = self.settings.get("notifications")
        return bool(section.get("show_in_app", True)) if isinstance(section, dict) else True

    def tray_toast_enabled(self) -> bool:
        if self.settings is None:
            return True
        section = self.settings.get("notifications")
        return bool(section.get("tray_toast", True)) if isinstance(section, dict) else True


__all__ = ["NotificationCenter", "Notification", "Level"]
