"""
تحسينات أداء ويندوز الحقيقية — كل تعديل قابل للتراجع ومُسجَّل.

كل تعديل هنا:
- يقرأ القيمة السابقة أولاً ويحفظها في سجل التغييرات (Undo بنقرة واحدة).
- يحترم الوضع التجريبي.
- يرجع ActionResult برسالة عربية واضحة وما إذا كان يحتاج إعادة تشغيل.
"""

from __future__ import annotations

import logging
import re

from src.core.results import ActionResult
from src.utils.registry import delete_value, read_value, registry_available, winreg, write_value
from src.utils.winapi import IS_WINDOWS, is_admin, run_silent

logger = logging.getLogger(__name__)

ULTIMATE_PERFORMANCE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"
HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
BALANCED_GUID = "381b4222-f694-41f0-9685-ff5bb260df2e"
POWER_SAVER_GUID = "a1841308-3541-4fab-bc81-f71556f20b4a"

_POWER_PLAN_NAMES = {
    HIGH_PERFORMANCE_GUID: "الأداء العالي",
    BALANCED_GUID: "المتوازنة",
    POWER_SAVER_GUID: "موفّر الطاقة",
    ULTIMATE_PERFORMANCE_GUID: "الأداء المطلق",
}

_GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

# مسارات الريجستري المستخدمة (مرة واحدة، بدون تكرار نصوص)
_PATH_VISUAL_EFFECTS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
_PATH_BACKGROUND_APPS = r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
_PATH_TRANSPARENCY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_PATH_DESKTOP = r"Control Panel\Desktop"
_PATH_WINDOW_METRICS = r"Control Panel\Desktop\WindowMetrics"
_PATH_POWER = r"SYSTEM\CurrentControlSet\Control\Session Manager\Power"
_PATH_GRAPHICS = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
_PATH_MEMORY_INTEGRITY = (
    r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity"
)
_PATH_FILESYSTEM = r"SYSTEM\CurrentControlSet\Control\FileSystem"


class PerformanceTweaks:
    """تطبيق/عكس تحسينات أداء ويندوز المعروفة."""

    def __init__(self, settings_manager, journal=None, notifier=None):
        self.settings = settings_manager
        self.journal = journal
        self.notifier = notifier
        if journal is not None:
            journal.register_undo_handler("registry_tweak", self._undo_registry_tweak)
            journal.register_undo_handler("power_plan", self._undo_power_plan)

    # ------------------------------------------------------------------
    def _test_mode(self) -> bool:
        return bool(self.settings.get("test_mode")) if self.settings else False

    def _record(self, kind: str, description: str, data: dict) -> None:
        if self.journal is not None:
            self.journal.record(kind, description, data)

    def _preview(self, text: str) -> ActionResult:
        return ActionResult(True, f"[وضع المعاينة] {text}")

    # ------------------------------------------------------------------
    # خطة الطاقة
    # ------------------------------------------------------------------
    def get_active_power_plan(self) -> tuple[str | None, str]:
        """(GUID, الاسم) لخطة الطاقة النشطة حاليًا."""
        if not IS_WINDOWS:
            return None, "غير متاح"
        result = run_silent(["powercfg", "/getactivescheme"], timeout=30)
        if not result.ok:
            return None, "تعذر القراءة"
        match = _GUID_RE.search(result.stdout)
        if not match:
            return None, "غير معروفة"
        guid = match.group(0).lower()
        return guid, _POWER_PLAN_NAMES.get(guid, "خطة مخصصة")

    def set_power_plan(self, guid: str, label: str) -> ActionResult:
        if not IS_WINDOWS:
            return ActionResult(False, "خطة الطاقة متاحة على ويندوز فقط.")
        previous, previous_name = self.get_active_power_plan()
        if self._test_mode():
            return self._preview(f"كان سيتم تفعيل خطة {label}.")
        result = run_silent(["powercfg", "/setactive", guid], timeout=30)
        if result.ok:
            self._record("power_plan", f"تفعيل خطة الطاقة: {label}", {"previous": previous})
            return ActionResult(True, f"تم تفعيل خطة {label}.")
        # بعض أنظمة ويندوز ترجع خطأ عند نفس الخطة النشطة
        if previous and previous.lower() == guid.lower():
            return ActionResult(True, f"خطة {label} مفعّلة مسبقًا.")
        return ActionResult(False, f"تعذر تفعيل خطة {label}.", details=result.output)

    def set_high_performance_power_plan(self) -> ActionResult:
        return self.set_power_plan(HIGH_PERFORMANCE_GUID, "الأداء العالي")

    def set_balanced_power_plan(self) -> ActionResult:
        return self.set_power_plan(BALANCED_GUID, "المتوازنة")

    def unlock_ultimate_performance(self) -> ActionResult:
        """فتح وتفعيل خطة 'الأداء المطلق' المخفية (Ultimate Performance)."""
        if not IS_WINDOWS:
            return ActionResult(False, "خطة الطاقة متاحة على ويندوز فقط.")
        if self._test_mode():
            return self._preview("كان سيتم فتح وتفعيل خطة الأداء المطلق.")

        previous, _ = self.get_active_power_plan()
        # الخطة قد تكون موجودة مسبقًا (اسمها يحمل نسخة مكررة) — نتحقق أولًا.
        existing_guid = self._find_ultimate_scheme()
        if existing_guid:
            result = self.set_power_plan(existing_guid, "الأداء المطلق")
            if result.success:
                self._record("power_plan", "تفعيل خطة الطاقة: الأداء المطلق", {"previous": previous})
            return result

        result = run_silent(["powercfg", "-duplicatescheme", ULTIMATE_PERFORMANCE_GUID], timeout=60)
        if not result.ok:
            return ActionResult(False, "تعذر فتح خطة الأداء المطلق.", details=result.output)
        match = _GUID_RE.search(result.stdout)
        if not match:
            return ActionResult(False, "فُتحت الخطة لكن تعذر قراءة معرفها الجديد.", details=result.stdout)
        new_guid = match.group(0)
        activate = run_silent(["powercfg", "/setactive", new_guid], timeout=30)
        if activate.ok:
            self._record("power_plan", "تفعيل خطة الطاقة: الأداء المطلق", {"previous": previous})
            return ActionResult(True, "تم تفعيل خطة الأداء المطلق (Ultimate Performance).")
        return ActionResult(False, "تعذر تفعيل خطة الأداء المطلق.", details=activate.output)

    def _find_ultimate_scheme(self) -> str | None:
        result = run_silent(["powercfg", "/list"], timeout=30)
        if not result.ok:
            return None
        current = ""
        for line in result.stdout.splitlines():
            match = _GUID_RE.search(line)
            if match:
                current = match.group(0)
            if "Ultimate" in line or "الأداء المطلق" in line or "ultimate" in line.lower():
                if current:
                    return current
        return None

    def _undo_power_plan(self, entry: dict) -> tuple[bool, str]:
        previous = (entry.get("data") or {}).get("previous")
        if not previous:
            return False, "لا توجد خطة سابقة محفوظة."
        result = run_silent(["powercfg", "/setactive", previous], timeout=30)
        if result.ok:
            return True, "تمت إعادة خطة الطاقة السابقة."
        return False, "تعذرت إعادة خطة الطاقة السابقة."

    # ------------------------------------------------------------------
    # تعديلات الريجستري (مع تراجع عام)
    # ------------------------------------------------------------------
    def _apply_registry_tweak(
        self,
        path: str,
        name: str,
        value,
        description: str,
        root=None,
        needs_restart: bool = False,
        value_type=None,
        requires_admin: bool = True,
    ) -> ActionResult:
        if not registry_available():
            return ActionResult(False, "الريجستري غير متوفر على هذا النظام.")
        if root is None:
            root = winreg.HKEY_CURRENT_USER
        if requires_admin and root == winreg.HKEY_LOCAL_MACHINE and not is_admin():
            return ActionResult(False, f"{description} يتطلب صلاحيات مدير.")

        previous = read_value(root, path, name, None)
        if previous == value:
            return ActionResult(True, f"{description} مطبّق مسبقًا.")

        if self._test_mode():
            return self._preview(f"كان سيتم تطبيق: {description}")

        if not write_value(root, path, name, value, value_type):
            return ActionResult(False, f"تعذر تطبيق: {description}")

        self._record(
            "registry_tweak",
            description,
            {"path": path, "name": name, "previous": previous,
             "hive": "HKLM" if root == winreg.HKEY_LOCAL_MACHINE else "HKCU"},
        )
        message = f"تم: {description}."
        if needs_restart:
            message += " يحتاج إعادة تشغيل ليظهر الأثر."
        return ActionResult(True, message, needs_restart=needs_restart)

    def _undo_registry_tweak(self, entry: dict) -> tuple[bool, str]:
        data = entry.get("data", {})
        root = winreg.HKEY_LOCAL_MACHINE if data.get("hive") == "HKLM" else winreg.HKEY_CURRENT_USER
        previous = data.get("previous")
        if previous is None:
            ok = delete_value(root, data.get("path", ""), data.get("name", ""))
            return (ok, "تمت إزالة القيمة التي أضافها البرنامج." if ok else "تعذر التراجع.")
        ok = write_value(root, data.get("path", ""), data.get("name", ""), previous)
        return (True, "تمت استعادة القيمة السابقة.") if ok else (False, "تعذرت استعادة القيمة السابقة.")

    # ------------------------------------------------------------------
    # المؤثرات البصرية والواجهة
    # ------------------------------------------------------------------
    def set_visual_effects_best_performance(self) -> ActionResult:
        """ضبط المؤثرات البصرية على 'أفضل أداء' (يقلل استهلاك المعالج/الذاكرة)."""
        return self._apply_registry_tweak(
            _PATH_VISUAL_EFFECTS, "VisualFXSetting", 2,
            "ضبط المؤثرات البصرية على 'أفضل أداء'", needs_restart=False,
        )

    def disable_transparency(self) -> ActionResult:
        return self._apply_registry_tweak(
            _PATH_TRANSPARENCY, "EnableTransparency", 0, "تعطيل شفافية الواجهة",
        )

    def disable_animations(self) -> ActionResult:
        return self._apply_registry_tweak(
            _PATH_WINDOW_METRICS, "MinAnimate", "0", "تعطيل حركات النوافذ",
            value_type=winreg.REG_SZ if registry_available() else None,
        )

    def set_menu_delay_fast(self) -> ActionResult:
        return self._apply_registry_tweak(
            _PATH_DESKTOP, "MenuShowDelay", "0", "تسريع ظهور القوائم",
            value_type=winreg.REG_SZ if registry_available() else None,
        )

    def disable_background_apps(self) -> ActionResult:
        """منع تطبيقات المتجر (UWP) من العمل بالخلفية بدون استخدام."""
        return self._apply_registry_tweak(
            _PATH_BACKGROUND_APPS, "GlobalUserDisabled", 1,
            "تعطيل تطبيقات الخلفية (UWP)",
        )

    def enable_background_apps(self) -> ActionResult:
        return self._apply_registry_tweak(
            _PATH_BACKGROUND_APPS, "GlobalUserDisabled", 0,
            "إعادة تفعيل تطبيقات الخلفية (UWP)",
        )

    # ------------------------------------------------------------------
    # تعديلات النظام (HKLM — تتطلب صلاحيات مدير)
    # ------------------------------------------------------------------
    def set_fast_startup(self, enabled: bool) -> ActionResult:
        return self._apply_registry_tweak(
            _PATH_POWER, "HiberbootEnabled", 1 if enabled else 0,
            ("تفعيل" if enabled else "تعطيل") + " الإقلاع السريع",
            root=winreg.HKEY_LOCAL_MACHINE if registry_available() else None,
            needs_restart=True,
        )

    def set_hardware_gpu_scheduling(self, enabled: bool) -> ActionResult:
        """جدولة GPU بالعتاد (HAGS) — قد تحسّن الاستجابة على بطاقات حديثة."""
        return self._apply_registry_tweak(
            _PATH_GRAPHICS, "HwSchMode", 2 if enabled else 1,
            ("تفعيل" if enabled else "تعطيل") + " جدولة GPU بالعتاد (HAGS)",
            root=winreg.HKEY_LOCAL_MACHINE if registry_available() else None,
            needs_restart=True,
        )

    def optimize_ntfs_last_access(self) -> ActionResult:
        """تقليل كتابات القرص عبر إيقاف تحديث 'آخر وصول' للملفات (إعداد ويندوز القياسي)."""
        return self._apply_registry_tweak(
            _PATH_FILESYSTEM, "NtfsDisableLastAccessUpdate", 1,
            "تقليل كتابات القرص (تعطيل تحديث وقت آخر وصول)",
            root=winreg.HKEY_LOCAL_MACHINE if registry_available() else None,
        )

    def toggle_memory_integrity(self, enabled: bool, confirm: bool = False) -> ActionResult:
        """
        تعديل متقدم: تعطيل Memory Integrity (VBS) يرفع الأداء ببعض الحالات
        لكنه يقلل الحماية ضد برمجيات خبيثة على مستوى kernel. لا يُنفّذ إلا
        بتأكيد صريح من المستخدم.
        """
        if not confirm:
            return ActionResult(
                False,
                "تعديل متقدم يقلل الحماية ضد برمجيات kernel (rootkits) مقابل أداء أعلى. "
                "مطلوب تأكيد صريح من المستخدم.",
            )
        return self._apply_registry_tweak(
            _PATH_MEMORY_INTEGRITY, "Enabled", 1 if enabled else 0,
            ("تفعيل" if enabled else "تعطيل") + " Memory Integrity",
            root=winreg.HKEY_LOCAL_MACHINE if registry_available() else None,
            needs_restart=True,
        )

    # ------------------------------------------------------------------
    # حالة التحسينات الحالية (لعرضها بجانب كل زر في الواجهة)
    # ------------------------------------------------------------------
    def current_state(self) -> dict:
        if not registry_available():
            return {"available": False}
        state = {
            "available": True,
            "visual_effects_best_performance": read_value(
                winreg.HKEY_CURRENT_USER, _PATH_VISUAL_EFFECTS, "VisualFXSetting") == 2,
            "background_apps_disabled": read_value(
                winreg.HKEY_CURRENT_USER, _PATH_BACKGROUND_APPS, "GlobalUserDisabled") == 1,
            "animations_disabled": str(read_value(
                winreg.HKEY_CURRENT_USER, _PATH_WINDOW_METRICS, "MinAnimate", "")) == "0",
            "fast_startup": read_value(
                winreg.HKEY_LOCAL_MACHINE, _PATH_POWER, "HiberbootEnabled") == 1,
            "hags": read_value(winreg.HKEY_LOCAL_MACHINE, _PATH_GRAPHICS, "HwSchMode") == 2,
        }
        if IS_WINDOWS:
            _guid, name = self.get_active_power_plan()
            state["power_plan"] = name
        return state

    def apply_recommended_bundle(self) -> list[tuple[str, ActionResult]]:
        """حزمة التحسينات الآمنة الموصى بها (بدون أي تعديل أمني متقدم)."""
        steps = [
            ("خطة الأداء العالي", self.set_high_performance_power_plan),
            ("المؤثرات البصرية", self.set_visual_effects_best_performance),
            ("تعطيل تطبيقات الخلفية", self.disable_background_apps),
            ("تعطيل الشفافية", self.disable_transparency),
            ("تسريع القوائم", self.set_menu_delay_fast),
        ]
        results = []
        for label, fn in steps:
            try:
                results.append((label, fn()))
            except Exception as exc:  # لا نوقف بقية الحزمة بسبب خطوة واحدة
                logger.exception("Bundle step failed: %s", label)
                results.append((label, ActionResult(False, f"فشل التنفيذ: {exc}")))
        return results


__all__ = ["PerformanceTweaks", "ULTIMATE_PERFORMANCE_GUID"]
