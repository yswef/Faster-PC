"""
مراقبة الأعطال وصحة النظام (قراءة فقط).

يجمع من مصادر ويندوز الرسمية:
- انهيارات التطبيقات وتعليقها من سجل الأحداث (Application log:
  Application Error 1000, Windows Error Reporting 1001, Application Hang 1002,
  .NET Runtime 1026) — بدون أي أداة خارجية، عبر PowerShell بصمت.
- أخطاء النظام الحرجة (System log: Level 1/2) آخر 24 ساعة.
- المساحة المنخفضة على الأقراص.
- معلومات النسخة ووقت التشغيل.

النتيجة تُعرض في تبويب "الصحة والأعطال" وتُرسل تنبيهات عند وجود عطل جديد،
بدل ما يكتشف المستخدم لاحقًا أن برنامجًا كان يتعطل من أسبوع.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

from src.utils.winapi import IS_WINDOWS, get_windows_info, run_powershell

logger = logging.getLogger(__name__)

_CRASH_EVENT_IDS = (1000, 1001, 1002, 1026)
_APP_NAME_RE = re.compile(r"([A-Za-z0-9_\-\.]+\.exe)", re.IGNORECASE)


class HealthMonitor(QObject):
    """فحص دوري لصحة النظام وإرسال إشارات عند اكتشاف مشاكل جديدة."""

    issue_found = Signal(dict)     # مشكلة جديدة تستحق إشعارًا
    report_ready = Signal(dict)    # تقرير كامل جاهز للعرض

    def __init__(self, settings_manager=None, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scan_now)
        self._seen_signatures: set[str] = set()
        self._first_scan_done = False
        self.last_report: dict = {}
        self._configure()

    # ------------------------------------------------------------------
    def _configure(self) -> None:
        section = {}
        if self.settings is not None:
            value = self.settings.get("health")
            if isinstance(value, dict):
                section = value
        self.enabled = bool(section.get("enabled", True))
        self.interval_min = max(5, int(section.get("check_interval_min", 30)))
        self.low_disk_gb = float(section.get("low_disk_gb", 5) or 5)
        self.watch_event_log = bool(section.get("watch_event_log", True))
        self.notify_crashes = bool(section.get("notify_crashes", True))

    def apply_settings(self) -> None:
        self._configure()
        self.start()

    def start(self) -> None:
        if self.enabled:
            self.timer.start(self.interval_min * 60 * 1000)
            QTimer.singleShot(2500, self.scan_now)  # فحص أولي بعد بدء الواجهة بقليل

    def stop(self) -> None:
        self.timer.stop()

    # ------------------------------------------------------------------
    def scan_now(self) -> dict:
        report = self.collect_report()
        self.last_report = report
        self.report_ready.emit(report)

        for issue in report.get("issues", []):
            signature = issue.get("signature", "")
            if signature in self._seen_signatures:
                continue
            self._seen_signatures.add(signature)
            if not self._first_scan_done:
                # في أول فحص لا نزعج المستخدم، نعرض فقط
                continue
            self.issue_found.emit(issue)

        self._first_scan_done = True
        return report

    # ------------------------------------------------------------------
    def collect_report(self) -> dict:
        report = {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "windows": get_windows_info(),
            "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
            "issues": [],
            "disks": [],
            "system_errors_24h": 0,
            "recent_crashes": [],
        }
        try:
            report["disks"] = self._disk_status(report["issues"])
        except Exception as exc:
            logger.debug("Disk check failed: %s", exc)
        try:
            if self.watch_event_log:
                crashes, system_errors = self._event_log_status()
                report["recent_crashes"] = crashes
                report["system_errors_24h"] = system_errors
                for crash in crashes[:10]:
                    signature = f"crash:{crash['event_id']}:{crash['timestamp']}:{crash['app']}"
                    report["issues"].append({
                        "type": "crash",
                        "severity": "warning",
                        "title": f"عطل في {crash['app']}",
                        "detail": f"{crash['kind']} — {crash['timestamp']}",
                        "app": crash["app"],
                        "signature": signature,
                    })
        except Exception as exc:
            logger.debug("Event log scan failed: %s", exc)
        return report

    # ------------------------------------------------------------------
    def _disk_status(self, issues: list[dict]) -> list[dict]:
        disks = []
        seen = set()
        partitions = psutil.disk_partitions(all=False) if IS_WINDOWS else psutil.disk_partitions(all=False)
        for part in partitions:
            if part.mountpoint in seen:
                continue
            seen.add(part.mountpoint)
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            free_gb = round(usage.free / (1024 ** 3), 1)
            entry = {
                "mount": part.mountpoint,
                "percent": round(usage.percent, 1),
                "free_gb": free_gb,
                "total_gb": round(usage.total / (1024 ** 3), 1),
            }
            disks.append(entry)
            if free_gb < self.low_disk_gb:
                issues.append({
                    "type": "disk",
                    "severity": "error" if free_gb < self.low_disk_gb / 2 else "warning",
                    "title": f"المساحة منخفضة على {part.mountpoint}",
                    "detail": f"المتبقي {free_gb} GB فقط من أصل {entry['total_gb']} GB.",
                    "signature": f"disk:{part.mountpoint}:{int(free_gb)}",
                })
        return disks

    # ------------------------------------------------------------------
    def _event_log_status(self) -> tuple[list[dict], int]:
        """قراءة سجل أحداث ويندوز عبر PowerShell مرة واحدة لكل فحص."""
        if not IS_WINDOWS:
            return [], 0

        minutes = 24 * 60
        script = f"""
$ErrorActionPreference='SilentlyContinue'
$start = (Get-Date).AddMinutes(-{minutes})
$crashes = Get-WinEvent -FilterHashtable @{{LogName='Application'; Id=1000,1001,1002,1026; StartTime=$start}} -MaxEvents 40 |
  Select-Object Id, TimeCreated, ProviderName, Message
$sys = Get-WinEvent -FilterHashtable @{{LogName='System'; Level=1,2; StartTime=$start}} -MaxEvents 200
$out = @{{
  crashes = @($crashes | ForEach-Object {{
     $msg = ($_.Message -replace "`r|`n", ' ')
     [PSCustomObject]@{{
       id = $_.Id
       time = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
       provider = $_.ProviderName
       message = $msg.Substring(0, [Math]::Min(600, $msg.Length))
     }}
  }})
  system_errors = @($sys).Count
}}
$out | ConvertTo-Json -Depth 4 -Compress
"""
        result = run_powershell(script, timeout=90)
        if not result.ok or not result.stdout.strip():
            logger.debug("Event log query failed: %s", result.output[:300])
            return [], 0

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            logger.debug("Could not parse event log JSON.")
            return [], 0

        crashes_raw = data.get("crashes") or []
        if isinstance(crashes_raw, dict):
            crashes_raw = [crashes_raw]

        crashes = []
        for item in crashes_raw:
            message = str(item.get("message") or "")
            match = _APP_NAME_RE.search(message)
            app = match.group(1) if match else (item.get("provider") or "تطبيق غير معروف")
            event_id = int(item.get("id") or 0)
            kind = {
                1000: "توقف مفاجئ (Application Error)",
                1001: "تقرير خطأ لويندوز",
                1002: "تطبيق توقف عن الاستجابة (Hang)",
                1026: "انهيار .NET",
            }.get(event_id, "عطل")
            crashes.append({
                "event_id": event_id,
                "app": app,
                "kind": kind,
                "timestamp": item.get("time") or "",
                "provider": item.get("provider") or "",
                "message": message[:400],
            })

        system_errors = int(data.get("system_errors") or 0)
        return crashes, system_errors

    # ------------------------------------------------------------------
    @staticmethod
    def summarize(report: dict) -> str:
        """ملخص نصي قصير للتقرير (يُستخدم في تقرير التشخيص المصدَّر)."""
        lines = ["Faster PC — تقرير صحة النظام", "=" * 40]
        win = report.get("windows", {})
        lines.append(f"النظام: {win.get('name', '?')} {win.get('version', '')} (بناء {win.get('build', '?')})")
        lines.append(f"مدة التشغيل: {report.get('uptime_hours', '?')} ساعة")
        lines.append(f"أخطاء النظام خلال 24 ساعة: {report.get('system_errors_24h', 0)}")
        lines.append("")
        lines.append("الأقراص:")
        for disk in report.get("disks", []):
            lines.append(f"  {disk['mount']}: متبقي {disk['free_gb']} GB ({disk['percent']}% ممتلئ)")
        crashes = report.get("recent_crashes", [])
        if crashes:
            lines.append("")
            lines.append("أحدث الأعطال:")
            for crash in crashes[:10]:
                lines.append(f"  [{crash['timestamp']}] {crash['app']} — {crash['kind']}")
        lines.append("")
        lines.append(f"تاريخ التقرير: {report.get('generated', '')}")
        return "\n".join(lines)


__all__ = ["HealthMonitor"]
