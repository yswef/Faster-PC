"""
مراقبة الأداء المباشرة — قلب تطوير المشروع.

يعطي:
- لقطة كاملة (نظام + قرص + شبكة + عمليات) محدّثة بفترة قابلة للضبط.
- تاريخ قصير (history) لعرض الرسوم البيانية (سباركلاين) لآخر N ثانية.
- رصد تجاوز الحدود (CPU/RAM/disk) بشكل مستمر مع مدة استمرار قبل التنبيه.
- رصد فتح/إغلاق العمليات (لعرض "أحدث البرامج فتحًا" وكشف البرامج الثقيلة).

كل شيء هنا للقراءة فقط — لا يعدّل النظام إطلاقًا.
"""

from __future__ import annotations

import logging
import time
from collections import deque

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class PerformanceMonitor(QObject):
    """مصدر واحد لكل أرقام الأداء في البرنامج (الواجهة تتصل وتُعرض فقط)."""

    sample = Signal(dict)              # لقطة كاملة كل فترة
    threshold_exceeded = Signal(str, float)   # (اسم المقياس، القيمة)
    process_started = Signal(str, int)        # (اسم العملية، pid)
    process_exited = Signal(str, int)

    METRICS = ("cpu", "ram", "disk")

    def __init__(self, settings_manager=None, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._history_len = 150
        self.cpu_history: deque[float] = deque(maxlen=self._history_len)
        self.ram_history: deque[float] = deque(maxlen=self._history_len)
        self.disk_history: deque[float] = deque(maxlen=self._history_len)

        self._last_disk_io = None
        self._last_net_io = None
        self._last_tick_time = None
        self._prev_pids: set[int] = set()
        self._over_since: dict[str, float | None] = {m: None for m in self.METRICS}
        self._notified: dict[str, bool] = {m: False for m in self.METRICS}

        self.last_sample: dict = {}
        self._configure_from_settings()
        psutil.cpu_percent(interval=None)  # تهيئة قياس المعالج

    # ------------------------------------------------------------------
    def _configure_from_settings(self) -> None:
        section = {}
        if self.settings is not None:
            value = self.settings.get("monitoring")
            if isinstance(value, dict):
                section = value
        self.enabled = bool(section.get("enabled", True))
        self.interval_ms = max(1, int(section.get("interval_sec", 2))) * 1000
        self.top_n = max(3, int(section.get("top_processes", 8)))
        self.thresholds = section.get("thresholds") if isinstance(section.get("thresholds"), dict) else {}
        self.notify_on_threshold = bool(section.get("notify_on_threshold", True))
        self.track_events = bool(section.get("track_process_events", True))
        history_seconds = max(60, int(section.get("history_seconds", 300)))
        new_len = max(30, history_seconds // max(1, self.interval_ms // 1000))
        if new_len != self._history_len or any(
            getattr(self, f"{m}_history").maxlen != new_len for m in self.METRICS
        ):
            self._history_len = new_len
            # deque.maxlen غير قابل للتعديل — نُنشئ deques جديدة مع الاحتفاظ بالبيانات
            for metric in self.METRICS:
                attribute = f"{metric}_history"
                old = getattr(self, attribute)
                setattr(self, attribute, deque(list(old)[-new_len:], maxlen=new_len))

    def apply_settings(self) -> None:
        """يُستدعى بعد تغيير إعدادات المراقبة من نافذة الإعدادات."""
        self._configure_from_settings()
        self.start()

    def start(self) -> None:
        if self.enabled:
            self.timer.start(self.interval_ms)
            self._tick()

    def stop(self) -> None:
        self.timer.stop()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        try:
            snapshot = self.collect()
        except Exception as exc:  # أي مشكلة هنا لا يجوز أن تُسقط المراقبة أو الواجهة
            logger.debug("Performance sample failed: %s", exc)
            return
        self.last_sample = snapshot
        self.sample.emit(snapshot)

    def collect(self) -> dict:
        """جمع لقطة كاملة — قابلة للاستدعاء من أي مكان (اختبارات، تقارير)."""
        now = time.monotonic()
        elapsed = (now - self._last_tick_time) if self._last_tick_time else 0.0
        self._last_tick_time = now

        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        root = self._system_drive()
        disk = psutil.disk_usage(root)

        disk_io = self._io_rate(psutil.disk_io_counters(), "disk", elapsed)
        net_io = self._io_rate(psutil.net_io_counters(), "net", elapsed)

        processes = self._top_processes()
        self._track_process_events()

        snapshot = {
            "time": time.time(),
            "cpu_percent": round(cpu, 1),
            "cpu_count": psutil.cpu_count(logical=True) or 1,
            "cpu_freq_mhz": self._cpu_freq(),
            "ram_percent": round(memory.percent, 1),
            "ram_used_mb": round(memory.used / (1024 ** 2), 0),
            "ram_total_mb": round(memory.total / (1024 ** 2), 0),
            "swap_percent": round(swap.percent, 1),
            "disk_percent": round(disk.percent, 1),
            "disk_free_gb": round(disk.free / (1024 ** 3), 1),
            "disk_total_gb": round(disk.total / (1024 ** 3), 1),
            "disk_read_mb_s": disk_io["read"],
            "disk_write_mb_s": disk_io["write"],
            "net_up_kb_s": net_io["write"],
            "net_down_kb_s": net_io["read"],
            "process_count": len(psutil.pids()),
            "uptime_seconds": int(time.time() - psutil.boot_time()),
            "top_processes": processes,
        }

        self.cpu_history.append(snapshot["cpu_percent"])
        self.ram_history.append(snapshot["ram_percent"])
        self.disk_history.append(snapshot["disk_percent"])
        snapshot["history"] = {
            "cpu": list(self.cpu_history),
            "ram": list(self.ram_history),
            "disk": list(self.disk_history),
        }

        if self.notify_on_threshold:
            self._check_thresholds(snapshot, now)
        return snapshot

    # ------------------------------------------------------------------
    def _system_drive(self) -> str:
        from src.utils.winapi import windows_drive

        return windows_drive()

    def _cpu_freq(self) -> float:
        try:
            freq = psutil.cpu_freq()
            return round(freq.current, 0) if freq else 0.0
        except Exception:
            return 0.0

    def _io_rate(self, counters, kind: str, elapsed: float) -> dict:
        if counters is None:
            return {"read": 0.0, "write": 0.0}
        # ملاحظة: عدّادات القرص فيها read_bytes/write_bytes، وعدّادات الشبكة
        # فيها bytes_recv/bytes_sent — نتعامل مع الحالتين بدون استثناءات.
        attribute = "_last_disk_io" if kind == "disk" else "_last_net_io"
        previous = getattr(self, attribute)
        setattr(self, attribute, counters)
        if previous is None or elapsed <= 0:
            return {"read": 0.0, "write": 0.0}
        if kind == "disk":
            read_diff = max(0, counters.read_bytes - previous.read_bytes)
            write_diff = max(0, counters.write_bytes - previous.write_bytes)
        else:  # عدّادات الشبكة تستخدم bytes_sent/bytes_recv
            read_diff = max(0, getattr(counters, "bytes_recv", 0) - getattr(previous, "bytes_recv", 0))
            write_diff = max(0, getattr(counters, "bytes_sent", 0) - getattr(previous, "bytes_sent", 0))
        if kind == "disk":
            factor = 1024 ** 2
            return {"read": round(read_diff / factor / elapsed, 2), "write": round(write_diff / factor / elapsed, 2)}
        factor = 1024
        return {"read": round(read_diff / factor / elapsed, 1), "write": round(write_diff / factor / elapsed, 1)}

    def _top_processes(self) -> list[dict]:
        results = []
        for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                results.append({
                    "pid": info["pid"],
                    "name": info.get("name") or "?",
                    "memory_mb": round((mem.rss if mem else 0) / (1024 ** 2), 1),
                    "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        results.sort(key=lambda p: (p["cpu_percent"], p["memory_mb"]), reverse=True)
        return results[: self.top_n]

    def _track_process_events(self) -> None:
        if not self.track_events:
            return
        try:
            current = set(psutil.pids())
        except Exception:
            return
        if self._prev_pids:
            for pid in current - self._prev_pids:
                try:
                    name = psutil.Process(pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                self.process_started.emit(name, pid)
            for pid in self._prev_pids - current:
                self.process_exited.emit("", pid)
        self._prev_pids = current

    # ------------------------------------------------------------------
    def _check_thresholds(self, snapshot: dict, now: float) -> None:
        """
        تنبيه فقط عند استمرار التجاوز مدة كافية (sustained_seconds) — يمنع
        إزعاج المستخدم بقفزات لحظية في المعالج.
        """
        raw_sustained = self.thresholds.get("sustained_seconds", 15)
        sustained = float(raw_sustained) if raw_sustained is not None else 15.0
        mapping = {
            "cpu": snapshot["cpu_percent"],
            "ram": snapshot["ram_percent"],
            "disk": snapshot["disk_percent"],
        }
        keys = {"cpu": "cpu_percent", "ram": "ram_percent", "disk": "disk_percent"}
        for metric, value in mapping.items():
            raw_limit = self.thresholds.get(keys[metric], 90)
            limit = float(raw_limit) if raw_limit is not None else 90.0
            if value >= limit:
                if self._over_since[metric] is None:
                    self._over_since[metric] = now
                elif not self._notified[metric] and (now - self._over_since[metric]) >= sustained:
                    self._notified[metric] = True
                    self.threshold_exceeded.emit(metric, value)
            else:
                if self._notified[metric] and value < limit * 0.85:
                    self._notified[metric] = False
                self._over_since[metric] = None


__all__ = ["PerformanceMonitor"]
