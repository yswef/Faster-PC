import logging
import subprocess
import winreg

logger = logging.getLogger(__name__)

ULTIMATE_PERFORMANCE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"


class TweakResult:
    def __init__(self, success: bool, message: str, needs_restart: bool = False):
        self.success = success
        self.message = message
        self.needs_restart = needs_restart

    def __repr__(self):
        return f"TweakResult(success={self.success}, message={self.message!r})"


class PerformanceTweaks:
    """
    مجموعة تحسينات أداء ويندوز الحقيقية والمُختبرة (مصدرها إرشادات تحسين
    أداء ويندوز 11 الحالية). كل تعديل هنا معروف ورجعي (reversible) ومفصول
    عن أي تعديل يمس أمان النظام بشكل جوهري.
    """

    def __init__(self, settings_manager):
        self.settings = settings_manager

    def _dry(self):
        return bool(self.settings.get("test_mode"))

    def _run(self, cmd, timeout=30):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
            return r.returncode, r.stdout, r.stderr
        except (subprocess.SubprocessError, OSError) as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    def set_high_performance_power_plan(self) -> TweakResult:
        if self._dry():
            return TweakResult(True, "[TEST MODE] كان سيتم تفعيل خطة الأداء العالي.")
        # GUID الثابت لخطة "أداء عالٍ" المدمجة بويندوز
        code, out, err = self._run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"])
        if code == 0:
            return TweakResult(True, "تم تفعيل خطة الأداء العالي.")
        return TweakResult(False, f"تعذر تفعيل خطة الأداء العالي: {err or out}")

    def unlock_ultimate_performance(self) -> TweakResult:
        """يفعّل خطة 'الأداء المطلق' المخفية (Ultimate Performance) عبر powercfg."""
        if self._dry():
            return TweakResult(True, "[TEST MODE] كان سيتم فتح وتفعيل خطة الأداء المطلق.")
        code, out, err = self._run(
            ["powercfg", "-duplicatescheme", ULTIMATE_PERFORMANCE_GUID]
        )
        if code != 0:
            return TweakResult(False, f"تعذر فتح خطة الأداء المطلق: {err or out}")
        # استخراج الـ GUID الجديد من مخرجات powercfg وتفعيله
        new_guid = None
        for token in out.split():
            if token.count("-") == 4 and len(token) == 36:
                new_guid = token
                break
        if new_guid:
            self._run(["powercfg", "/setactive", new_guid])
        return TweakResult(True, "تم تفعيل خطة الأداء المطلق (Ultimate Performance).")

    def set_visual_effects_best_performance(self) -> TweakResult:
        """يعطّل الأنيميشن/الشفافية/الظلال لتقليل استهلاك المعالج، خصوصًا على أجهزة رام محدودة."""
        if self._dry():
            return TweakResult(True, "[TEST MODE] كان سيتم ضبط المؤثرات البصرية على 'أفضل أداء'.")
        try:
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
            ) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
            return TweakResult(True, "تم ضبط المؤثرات البصرية على 'أفضل أداء'. قد تحتاج تسجيل خروج/دخول ليظهر التأثير كاملاً.")
        except OSError as e:
            return TweakResult(False, f"تعذر تعديل إعدادات المؤثرات البصرية: {e}")

    def toggle_background_apps(self, enabled: bool) -> TweakResult:
        """يمنع تطبيقات المتجر (UWP) من العمل بالخلفية بدون استخدام - يوفر رام وCPU."""
        if self._dry():
            return TweakResult(True, f"[TEST MODE] كان سيتم {'تفعيل' if enabled else 'تعطيل'} تطبيقات الخلفية.")
        try:
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
            ) as key:
                winreg.SetValueEx(key, "GlobalUserDisabled", 0, winreg.REG_DWORD, 0 if enabled else 1)
            return TweakResult(True, f"تم {'تفعيل' if enabled else 'تعطيل'} تطبيقات الخلفية.")
        except OSError as e:
            return TweakResult(False, f"تعذر تعديل إعداد تطبيقات الخلفية: {e}")

    def toggle_fast_startup(self, enabled: bool) -> TweakResult:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                0, winreg.KEY_SET_VALUE,
            ) as key:
                if self._dry():
                    return TweakResult(True, f"[TEST MODE] كان سيتم {'تفعيل' if enabled else 'تعطيل'} Fast Startup.")
                winreg.SetValueEx(key, "HiberbootEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
            return TweakResult(True, f"تم {'تفعيل' if enabled else 'تعطيل'} Fast Startup.", needs_restart=True)
        except (PermissionError, OSError) as e:
            return TweakResult(False, f"تعذر تعديل Fast Startup (يتطلب صلاحيات مدير): {e}")

    def toggle_hardware_gpu_scheduling(self, enabled: bool) -> TweakResult:
        """جدولة GPU بالعتاد (HAGS) - قد تقلل زمن الاستجابة على كروت رسومات حديثة. تحتاج إعادة تشغيل."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                0, winreg.KEY_SET_VALUE,
            ) as key:
                if self._dry():
                    return TweakResult(True, f"[TEST MODE] كان سيتم {'تفعيل' if enabled else 'تعطيل'} HAGS.")
                winreg.SetValueEx(key, "HwSchMode", 0, winreg.REG_DWORD, 2 if enabled else 1)
            return TweakResult(True, f"تم {'تفعيل' if enabled else 'تعطيل'} جدولة GPU بالعتاد (HAGS).", needs_restart=True)
        except (PermissionError, OSError) as e:
            return TweakResult(False, f"تعذر تعديل HAGS (يتطلب صلاحيات مدير): {e}")

    # ------------------------------------------------------------------
    # تعديل متقدم واختياري بوضوح - غير مرتبط بأي زر "تسريع سريع"، ويحتاج
    # confirm=True صريح من الواجهة بعد تحذير للمستخدم. تعطيل هذا الإعداد
    # (Memory Integrity / VBS) يقلل الحماية ضد البرمجيات الخبيثة على مستوى
    # النواة (rootkits)، مقابل مكسب أداء ملحوظ ببعض الألعاب/التطبيقات
    # الثقيلة. نفس المقايضة اللي تعرضها أدوات تحسين الألعاب المعروفة،
    # ونتركها اختيار واعٍ للمستخدم وليست مفعّلة تلقائيًا بأي سيناريو.
    # ------------------------------------------------------------------
    def toggle_memory_integrity(self, enabled: bool, confirm: bool = False) -> TweakResult:
        if not confirm:
            return TweakResult(
                False,
                "هذا تعديل متقدم يقلل الحماية ضد البرمجيات الخبيثة على مستوى kernel "
                "(rootkits) مقابل مكسب أداء بالألعاب الثقيلة. مرّر confirm=True من "
                "الواجهة بعد تأكيد المستخدم صراحة.",
            )
        try:
            with winreg.CreateKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity",
            ) as key:
                if self._dry():
                    return TweakResult(True, f"[TEST MODE] كان سيتم {'تفعيل' if enabled else 'تعطيل'} Memory Integrity.")
                winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
            return TweakResult(
                True,
                f"تم {'تفعيل' if enabled else 'تعطيل'} Memory Integrity. يتطلب إعادة تشغيل الجهاز.",
                needs_restart=True,
            )
        except (PermissionError, OSError) as e:
            return TweakResult(False, f"تعذر تعديل Memory Integrity (يتطلب صلاحيات مدير): {e}")

    # ------------------------------------------------------------------
    def apply_recommended_bundle(self):
        """يطبّق حزمة التحسينات 'الآمنة افتراضيًا' دفعة واحدة (بدون Memory Integrity)."""
        results = []
        results.append(("power_plan", self.set_high_performance_power_plan()))
        results.append(("visual_effects", self.set_visual_effects_best_performance()))
        results.append(("background_apps", self.toggle_background_apps(enabled=False)))
        return results
