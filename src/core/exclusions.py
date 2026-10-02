"""
مدير الحماية — قلب أمان المشروع.

كل عملية إنهاء (سواء القائمة المحددة أو "إنهاء كل شي غير المستثنى") تمر من هنا
قبل psutil، وهذا يضمن ثلاث طبقات حماية:

1) محمية دائمًا (غير قابلة للتعديل من الإعدادات): عمليات إقلاع/نواة ويندوز —
   إنهاؤها يعني شاشة زرقاء أو خروج قسري مباشر.
2) محمية افتراضيًا: مكوّنات واجهة ويندوز وتطبيقات لا يجوز تعطيلها (explorer,
   تطبيق الصور, مضيف التطبيقات...) + أي برنامج يضيفه المستخدم بنفسه.
3) حماية ذاتية: البرنامج لا يقتل نفسه ولا أي عملية فرعية يشتغلها هو.

هذا الملف هو المرجع الوحيد لـ "وش يُقتل ووش لا" — لا تتخذ قرار القتل في أي
مكان آخر في المشروع.
"""

from __future__ import annotations

import logging
import os

import psutil

logger = logging.getLogger(__name__)

# عمليات لا يمكن إنهاؤها من هذا البرنامج نهائيًا (خطر توقف النظام فورًا).
HARD_PROTECTED_PROCESSES = {
    "system", "system idle process", "registry", "secure system",
    "memory compression", "idle",
    "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "dwm.exe", "fontdrvhost.exe",
    "logonui.exe", "lsaiso.exe", "sgrmbroker.exe",
}

# خدمات لا يُسمح بإيقافها نهائيًا (توقفها يعطل النظام أو شبكته/صوته فورًا).
HARD_PROTECTED_SERVICES = {
    "RpcSs", "DcomLaunch", "Power", "PlugPlay",
    "BrokerInfrastructure", "SystemEventsBroker",
}

# أشهر تطبيقات النظام التي تُستثنى مفهوميًا من أي قائمة قتل يقترحها المشروع.
_SYSTEM_PROCESS_NAMES = {
    "svchost.exe", "taskhostw.exe", "sppsvc.exe", "spoolsv.exe",
    "audiodg.exe", "conhost.exe", "dllhost.exe", "wmiprvse.exe",
    "searchindexer.exe", "securityhealthservice.exe", "msmpeng.exe",
    "nissrv.exe", "widgets.exe", "widgetservice.exe", "taskmgr.exe",
    "starthost.exe", "soffice.bin",
}


class ProtectionReason:
    """أسباب الحماية كنصوص جاهزة للعرض في السجل/الواجهة."""

    HARD = "عملية حرجة لويندوز — إنهاؤها يوقف النظام"
    EXCLUDED = "موجودة في قائمة عملياتك المستثناة"
    USER_PROTECTED = "من تطبيقاتك المحمية"
    OWN_APP = "عملية تابعة للبرنامج نفسه"
    SELF = "هذه عملية البرنامج نفسه"
    UNKNOWN = "تعذّر فحص العملية (صلاحيات غير كافية)"


class ProtectionManager:
    """يجيب عن سؤال واحد: هل يُسمح بإنهاء هذه العملية؟ ولأي سبب؟"""

    def __init__(self, settings_manager=None, own_pid: int | None = None):
        self.settings = settings_manager
        self.own_pid = own_pid if own_pid is not None else os.getpid()

    # ------------------------------------------------------------------
    def _setting_list(self, key: str) -> set[str]:
        if not self.settings:
            return set()
        return {str(x).strip().lower() for x in (self.settings.get(key) or []) if str(x).strip()}

    @property
    def exclusions(self) -> set[str]:
        return self._setting_list("process_exclusions")

    @property
    def user_protected_apps(self) -> set[str]:
        return self._setting_list("protected_apps")

    # ------------------------------------------------------------------
    def is_hard_protected(self, name: str) -> bool:
        return (name or "").strip().lower() in HARD_PROTECTED_PROCESSES

    def is_own_process_tree(self, proc: psutil.Process) -> bool:
        """True إذا كانت العملية هي البرنامج نفسه أو ابنة له (مثال: أمر تشغيله)."""
        try:
            if proc.pid == self.own_pid:
                return True
            for parent in proc.parents():
                if parent.pid == self.own_pid:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        return False

    def check_process(self, proc: psutil.Process | None = None, name: str | None = None,
                      pid: int | None = None) -> tuple[bool, str]:
        """
        فحص السماح بالإنهاء: يرجع (مسموح؟, السبب).
        يقبل: كائن psutil أو اسم/معرّف بشكل منفصل (فحص سريع بدون لمس النظام).
        """
        lower_name = (name or "").strip().lower()

        if not lower_name and proc is not None:
            try:
                lower_name = (proc.name() or "").strip().lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False, ProtectionReason.HARD

        if lower_name in HARD_PROTECTED_PROCESSES:
            return False, ProtectionReason.HARD

        if lower_name in self.user_protected_apps:
            return False, ProtectionReason.USER_PROTECTED
        if lower_name in self.exclusions:
            return False, ProtectionReason.EXCLUDED

        if proc is None and pid is not None:
            try:
                proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return True, ""  # العملية انتهت أصلًا — لا شيء لإنهائه
            except psutil.AccessDenied:
                return False, ProtectionReason.UNKNOWN

        if proc is not None:
            try:
                if proc.pid == self.own_pid:
                    return False, ProtectionReason.SELF
                if self.is_own_process_tree(proc):
                    return False, ProtectionReason.OWN_APP
            except psutil.NoSuchProcess:
                return True, ""
            except psutil.AccessDenied:
                return False, ProtectionReason.UNKNOWN

        # حماية مزدوجة: أي عملية جذرها مجلد ويندوز باسم حرج شائع
        if lower_name in _SYSTEM_PROCESS_NAMES and lower_name in self.exclusions:
            return False, ProtectionReason.EXCLUDED

        return True, ""

    # ------------------------------------------------------------------
    def is_service_protected(self, service_name: str) -> tuple[bool, str]:
        """هل يُسمح بتعديل حالة الخدمة؟"""
        name = (service_name or "").strip()
        for protected in HARD_PROTECTED_SERVICES:
            if name.lower() == protected.lower():
                return True, "خدمة أساسية في ويندوز — إيقافها يعطل النظام"
        if self.settings and name.lower() in {x.lower() for x in (self.settings.get("service_exclusions") or [])}:
            return True, "موجودة في قائمة الخدمات المستثناة بالإعدادات"
        return False, ""

    def add_app_to_protection(self, exe_name: str) -> bool:
        """إضافة برنامج لقائمة الحماية (يُستثنى من كل عمليات الإنهاء)."""
        if not self.settings or not exe_name:
            return False
        ok = self.settings.add_protected_app(exe_name)
        if ok:
            logger.info("Added to protection: %s", exe_name)
        return ok

    def remove_app_from_protection(self, exe_name: str) -> bool:
        if not self.settings:
            return False
        ok = self.settings.remove_protected_app(exe_name)
        if ok:
            logger.info("Removed from protection: %s", exe_name)
        return ok

    # ------------------------------------------------------------------
    def list_running_apps(self, include_system: bool = False) -> list[dict]:
        """
        قائمة التطبيقات الجارية (لاختيار برامج تُضاف للاستثناء):
        اسم العملية + المسار + الذاكرة + هل هي محمية حاليًا.
        """
        apps: dict[str, dict] = {}
        windows_dir = (os.environ.get("SystemRoot", r"C:\Windows") if os.name == "nt" else "/usr").lower()

        for proc in psutil.process_iter(["pid", "name", "memory_info", "exe"]):
            try:
                info = proc.info
                name = (info.get("name") or "").strip()
                if not name:
                    continue
                key = name.lower()
                exe_path = info.get("exe") or ""
                if not include_system and exe_path and exe_path.lower().startswith(windows_dir):
                    continue
                mem = info.get("memory_info")
                mem_mb = round(mem.rss / (1024 * 1024), 1) if mem else 0.0
                allowed, _reason = self.check_process(name=name, pid=info["pid"])
                entry = apps.get(key)
                if entry is None or mem_mb > entry["memory_mb"]:
                    apps[key] = {
                        "name": name,
                        "exe": exe_path,
                        "pid": info["pid"],
                        "memory_mb": mem_mb,
                        "protected": not allowed,
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return sorted(apps.values(), key=lambda a: a["memory_mb"], reverse=True)

    def summary(self) -> dict:
        """ملخص الحماية الحالي لعرضه في الواجهة."""
        return {
            "hard_protected_count": len(HARD_PROTECTED_PROCESSES),
            "exclusions_count": len(self.exclusions),
            "protected_apps_count": len(self.user_protected_apps),
            "hard_protected_services_count": len(HARD_PROTECTED_SERVICES),
        }


__all__ = [
    "ProtectionManager",
    "ProtectionReason",
    "HARD_PROTECTED_PROCESSES",
    "HARD_PROTECTED_SERVICES",
]
