"""
تنفيذ المهام في خيط منفصل (QThread) — الواجهة لا تتجمد أبدًا.

إصلاح مهم عن النسخة القديمة: كان الخيط قد يُحرَّر من الذاكرة بينما لا يزال
يعمل (garbage collection) لأن الواجهة لا تحتفظ إلا بمرجع مؤقت. هنا:
- كل خيط يبقى محفوظًا في مجموعة حتى ينتهي فعليًا.
- إشارة progress اختيارية لعرض تقدم العمليات الطويلة.
- any خطأ يُسجَّل مع اسم المهمة، فالرسالة تصل للمستخدم مفهومة.
"""

from __future__ import annotations

import logging
import traceback

from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


class TaskWorker(QThread):
    """يشغّل دالة في خيط منفصل ويُرجع النتيجة أو الخطأ عبر إشارات آمنة."""

    finished_ok = Signal(object)
    finished_error = Signal(str)
    progress = Signal(int, str)   # (النسبة %, الرسالة)

    def __init__(self, fn, *args, label: str = "", parent=None, **kwargs):
        super().__init__(parent)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.label = label or getattr(fn, "__name__", "مهمة")

    def run(self):  # noqa: D102
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:
            logger.error("فشلت المهمة '%s': %s\n%s", self.label, exc, traceback.format_exc())
            self.finished_error.emit(f"{self.label}: {exc}")


class TaskManager(QObject):
    """يدير كل الخيوط: يمنع فقدانها، ويعطي الواجهة حالة موحّدة."""
    task_started = Signal(str)
    task_finished = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: set[TaskWorker] = set()

    def run(self, fn, on_success=None, on_error=None, label: str = "", *args, **kwargs) -> TaskWorker:
        worker = TaskWorker(fn, *args, label=label, **kwargs)
        worker.setObjectName(label or "task")
        self._workers.add(worker)

        if on_success is not None:
            worker.finished_ok.connect(on_success)
        if on_error is not None:
            worker.finished_error.connect(on_error)

        def _cleanup():
            self._workers.discard(worker)
            ok = not worker.isInterruptionRequested()
            self.task_finished.emit(label or "مهمة", ok)

        worker.finished.connect(_cleanup)
        worker.finished.connect(worker.deleteLater)
        self.task_started.emit(label or "مهمة")
        worker.start()
        return worker

    def active_count(self) -> int:
        return len(self._workers)

    def wait_all(self, timeout_ms: int = 5000) -> None:
        for worker in list(self._workers):
            if worker.isRunning():
                worker.wait(timeout_ms)


__all__ = ["TaskWorker", "TaskManager"]
