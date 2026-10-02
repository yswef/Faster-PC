"""
إصلاح النظام — SFC، DISM، نقطة استعادة، DNS، فحص القرص.

كل الأوامر تُشغَّل بصمت تام (بدون أي نافذة cmd أو PowerShell ظاهرة)، بصلاحيات
مدير، وبدون shell حقيقي (لا حقن أوامر). كل دالة ترجع ActionResult برسالة عربية
مفيدة والتفاصيل الكاملة للمهتمين.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.core.results import ActionResult
from src.utils.winapi import IS_WINDOWS, is_admin, run_silent

logger = logging.getLogger(__name__)


def _ps_escape(text: str) -> str:
    """تهريب نص داخل علامات اقتباس مفردة في PowerShell."""
    return (text or "").replace("'", "''")


def is_admin_user() -> bool:
    """هل البرنامج يعمل بصلاحيات مدير؟ (تُستخدم في الواجهة لعرض تحذير)."""
    return is_admin()


class SystemRepair:
    """عمليات إصلاح ويندوز الرسمية مع معالجة أخطاء شاملة."""

    def __init__(self, settings_manager, notifier=None):
        self.settings = settings_manager
        self.notifier = notifier

    # ------------------------------------------------------------------
    def _require_windows(self, action: str) -> ActionResult | None:
        if not IS_WINDOWS:
            return ActionResult(False, f"{action} متاح على ويندوز فقط.")
        return None

    def _require_admin(self, action: str) -> ActionResult | None:
        if not is_admin():
            return ActionResult(
                False,
                f"{action} يتطلب تشغيل البرنامج كمسؤول (Run as Administrator).",
            )
        return None

    def _test_mode(self) -> bool:
        return bool(self.settings.get("test_mode")) if self.settings else False

    # ------------------------------------------------------------------
    def create_restore_point(self, description: str | None = None) -> ActionResult:
        """إنشاء نقطة استعادة قبل أي عملية خطرة (يُفضّل إنشاؤها قبل SFC/DISM)."""
        guard = self._require_windows("إنشاء نقطة استعادة") or self._require_admin("إنشاء نقطة استعادة")
        if guard:
            return guard
        if self._test_mode():
            return ActionResult(True, "[وضع المعاينة] كان سيتم إنشاء نقطة استعادة.")

        template = description or self.settings.get("restore_point_description") or "Faster PC - {date}"
        text = str(template).format(date=datetime.now().strftime("%Y-%m-%d %H:%M"))
        script = (
            "Checkpoint-Computer -Description '" + _ps_escape(text) + "' "
            "-RestorePointType 'MODIFY_SETTINGS'"
        )
        result = run_silent(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=600
        )
        if result.ok:
            return ActionResult(True, f"تم إنشاء نقطة استعادة: {text}")
        details = result.output
        hint = ""
        if "disabled" in details.lower() or "معطل" in details:
            hint = " تأكد أن حماية النظام (System Protection) مفعّلة على قرص النظام."
        elif "1440" in details or "24" in details:
            hint = " ويندوز يمنع إنشاء نقطة استعادة أكثر من مرة كل 24 ساعة افتراضيًا."
        return ActionResult(False, "تعذر إنشاء نقطة الاستعادة." + hint, details=details)

    def run_sfc(self) -> ActionResult:
        """فحص وإصلاح ملفات النظام (System File Checker)."""
        guard = self._require_windows("فحص SFC") or self._require_admin("فحص SFC")
        if guard:
            return guard
        if self._test_mode():
            return ActionResult(True, "[وضع المعاينة] كان سيتم تشغيل فحص SFC.")

        logger.info("Running SFC /scannow (قد يستغرق عدة دقائق)...")
        result = run_silent(["sfc", "/scannow"], timeout=3600)
        output = result.output
        lower = output.lower()
        if "did not find any integrity violations" in lower or "لم تجد أي انتهاكات" in output:
            return ActionResult(True, "SFC: ملفات النظام سليمة، لا توجد مشاكل.", details=output)
        if "successfully repaired" in lower or "تم الإصلاح بنجاح" in output:
            return ActionResult(True, "SFC: وُجدت ملفات تالفة وتم إصلاحها بنجاح.", details=output)
        if "unable to fix" in lower or "تعذر الإصلاح" in output:
            return ActionResult(
                False,
                "SFC: وُجدت ملفات تالفة ولم يتمكن من إصلاحها — جرّب DISM بعدها وأعد تشغيل الجهاز.",
                details=output,
            )
        if result.returncode == 0:
            return ActionResult(True, "SFC اكتمل بنجاح.", details=output)
        return ActionResult(False, "SFC انتهى بحالة غير متوقعة — راجع التفاصيل.", details=output)

    def run_dism(self) -> ActionResult:
        """إصلاح صورة ويندوز (DISM /RestoreHealth) — تتطلب إنترنت غالبًا."""
        guard = self._require_windows("إصلاح DISM") or self._require_admin("إصلاح DISM")
        if guard:
            return guard
        if self._test_mode():
            return ActionResult(True, "[وضع المعاينة] كان سيتم تشغيل DISM.")

        logger.info("Running DISM /RestoreHealth (قد يستغرق وقتًا طويلاً)...")
        result = run_silent(["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"], timeout=5400)
        output = result.output
        if result.ok or "The operation completed successfully" in output or "تمت العملية بنجاح" in output:
            return ActionResult(True, "DISM: تم إصلاح صورة النظام بنجاح.", details=output)
        if "0x800f081f" in output:
            return ActionResult(
                False,
                "DISM فشل بخطأ 0x800f081f: يحتاج ملفات المصدر أو اتصال إنترنت سليم.",
                details=output,
            )
        return ActionResult(False, "DISM واجه مشكلة — راجع التفاصيل.", details=output)

    def flush_dns(self) -> ActionResult:
        """تفريغ ذاكرة DNS المؤقتة — يحل مشاكل تصفح شائعة."""
        guard = self._require_windows("تفريغ ذاكرة DNS")
        if guard:
            return guard
        if self._test_mode():
            return ActionResult(True, "[وضع المعاينة] كان سيتم تفريغ ذاكرة DNS.")
        result = run_silent(["ipconfig", "/flushdns"], timeout=60)
        if result.ok:
            return ActionResult(True, "تم تفريغ ذاكرة DNS المؤقتة.")
        return ActionResult(False, "تعذر تفريغ ذاكرة DNS.", details=result.output)

    def reset_network_stack(self) -> ActionResult:
        """إعادة تعيين مكدس الشبكة (winsock + ip) — حل قوي لمشاكل الاتصال."""
        guard = self._require_windows("إعادة تعيين الشبكة") or self._require_admin("إعادة تعيين الشبكة")
        if guard:
            return guard
        if self._test_mode():
            return ActionResult(True, "[وضع المعاينة] كان سيتم إعادة تعيين مكدس الشبكة.")
        results = []
        for cmd in (["netsh", "winsock", "reset"], ["netsh", "int", "ip", "reset"]):
            results.append(run_silent(cmd, timeout=120))
        if any(r.ok for r in results):
            return ActionResult(
                True,
                "تمت إعادة تعيين مكدس الشبكة. يُنصح بإعادة تشغيل الجهاز.",
                needs_restart=True,
            )
        return ActionResult(False, "تعذرت إعادة تعيين الشبكة.", details="\n".join(r.output for r in results))

    def scan_disk(self, drive: str = "C:") -> ActionResult:
        """فحص القرص للأخطاء بدون تعطيل (/scan — لا يقفل القرص ولا يقطع عملك)."""
        guard = self._require_windows("فحص القرص")
        if guard:
            return guard
        letter = (drive or "C:").rstrip("\\/")
        if not letter.endswith(":"):
            letter += ":"
        if self._test_mode():
            return ActionResult(True, f"[وضع المعاينة] كان سيتم فحص القرص {letter}.")
        result = run_silent(["chkdsk", letter, "/scan"], timeout=3600)
        output = result.output
        found = any(
            phrase in output.lower()
            for phrase in ("found problems", "found errors", "windows has scanned")
        )
        if found and ("no problems" in output.lower() or "لم يتم العثور على مشاكل" in output):
            found = False
        if found:
            return ActionResult(
                False,
                f"وُجدت مشاكل على القرص {letter}. شغّل الإصلاح من موجّه الأوامر كمسؤول: chkdsk {letter} /f",
                details=output,
            )
        return ActionResult(True, f"القرص {letter} سليم — لم تُوجد أخطاء.", details=output)

    # ------------------------------------------------------------------
    def quick_health_checks(self) -> list[ActionResult]:
        """فحوصات سريعة آمنة لعرض ملخص الحالة (بدون تعديل أي شيء)."""
        checks: list[ActionResult] = []
        checks.append(ActionResult(
            True, "صلاحيات المدير متاحة." if is_admin() else "البرنامج يعمل بدون صلاحيات مدير.",
        ))
        return checks


__all__ = ["SystemRepair", "is_admin_user"]
