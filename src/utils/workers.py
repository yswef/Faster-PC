import logging
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class TaskWorker(QThread):
    """
    ينفّذ أي دالة (fn) بخيط منفصل عن واجهة المستخدم، حتى ما تتجمد النافذة
    أثناء عمليات طويلة (SFC/DISM/فحص مجلدات كبيرة). النتيجة أو أي استثناء
    يوصلان لخيط الواجهة عبر Signal بشكل آمن.
    """

    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished_ok.emit(result)
        except Exception as e:
            logger.exception(f"Background task failed: {e}")
            self.finished_error.emit(str(e))
