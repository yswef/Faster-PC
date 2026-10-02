"""
إدارة الإعدادات (config.json).

المزايا:
- كتابة ذرية (atomic): لا يتبقى ملف نصف مكتوب لو انقطعت الكهرباء/تعطل البرنامج.
- نسخة احتياطية تلقائية (config.json.bak) قبل كل حفظ، ونسخة تالفة
  (config.json.corrupt.bak) عند فشل القراءة.
- دمج عميق (deep merge) مع القيم الافتراضية: أي مفتاح جديد في نسخة أحدث
  يظهر تلقائيًا، وأي مفتاح ناقص لا يُفقد.
- ترقية تلقائية من بنية الإعدادات القديمة (schema 1) إلى الحالية (schema 2).
- تحقق من صحة القيم (validate) قبل الحفظ.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import tempfile

from src.utils.paths import config_path as default_config_path

logger = logging.getLogger(__name__)


def deep_merge(base: dict, incoming: dict) -> dict:
    """دمج عميق: القواميس تُدمج مفتاحًا بمفتاح، والقوائم/القيم تُستبدل."""
    result = copy.deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class SettingsManager:
    """تحميل/حفظ إعدادات التطبيق بشكل آمن مع حفظ تلقائي للنسخ الاحتياطية."""

    # القيم الافتراضية الكاملة — المرجع الوحيد لأي إعداد في البرنامج.
    DEFAULTS: dict = {
        "schema_version": 2,
        "setup_completed": False,

        # ---------- عام ----------
        "test_mode": False,               # وضع المعاينة: يسجل الإجراءات بدون تنفيذ
        "auto_clean_temp": False,         # تنظيف تلقائي عند بدء التشغيل
        "restore_point_description": "Faster PC Restore Point - {date}",

        # ---------- الاستثناءات والحماية ----------
        "process_exclusions": [
            # عمليات ويندوز الأساسية (واجهة/نواة/شل) — الحذف يمنعها افتراضيًا
            "system", "registry", "idle",
            "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
            "lsass.exe", "smss.exe", "dwm.exe", "fontdrvhost.exe",
            "sihost.exe", "ctfmon.exe", "explorer.exe", "shellhost.exe",
            "TextInputHost.exe", "RuntimeBroker.exe",
            "ShellExperienceHost.exe", "StartMenuExperienceHost.exe",
            "SearchHost.exe", "StartMenuHost.exe", "dllhost.exe",
            "WUDFHost.exe", "WUDFRd.exe", "WmiPrvSE.exe", "conhost.exe",
            "OpenConsole.exe", "WindowsTerminal.exe",
            # بايثون والواجهة (حتى لا يقتل البرنامج نفسه)
            "python.exe", "pythonw.exe", "fasterpc.exe", "faster pc.exe",
            # تطبيقات شائعة قد لا يقصد المستخدم إغلاقها
            "Microsoft.Photos.exe", "Photos.exe", "ApplicationFrameHost.exe",
        ],
        "protected_apps": [],              # تطبيقات أضافها المستخدم للحماية (أسماء .exe)
        "force_kill_list": [
            "pet.exe", "rsAppUI.exe",
            "BraveCrashHandler.exe", "BraveCrashHandler64.exe",
            "MicrosoftEdgeUpdate.exe",
        ],
        "service_exclusions": [
            "WinDefend", "EventLog", "RpcSs", "DcomLaunch", "Power",
            "AudioSrv", "AudioEndpointBuilder", "PlugPlay", "Themes",
            "gpsvc", "BFE", "mpssvc", "Dnscache", "Dhcp", "nsi",
            "Schedule", "ProfSvc", "StateRepository", "CryptSvc",
            "Winmgmt", "TrustedInstaller", "WlanSvc",
        ],

        # ---------- مراقبة الأداء ----------
        "monitoring": {
            "enabled": True,
            "interval_sec": 2,             # فترة تحديث اللوحة
            "history_seconds": 300,        # طول الرسم البياني الزمني
            "top_processes": 8,            # عدد العمليات الأعلى استهلاكًا المعروضة
            "thresholds": {
                "cpu_percent": 90,
                "ram_percent": 90,
                "disk_percent": 90,
                "sustained_seconds": 15,   # مدة استمرار التجاوز قبل التنبيه
            },
            "notify_on_threshold": True,
            "track_process_events": True,  # رصد العمليات الجديدة/المغلقة
        },

        # ---------- مراقبة الأعطال والأخطاء ----------
        "health": {
            "enabled": True,
            "check_interval_min": 30,      # فحص دوري لسجل الأحداث ومساحة القرص
            "watch_event_log": True,
            "low_disk_gb": 5,
            "notify_crashes": True,        # إشعار فوري عند انهيار تطبيق
            "crash_events_per_scan": 20,
        },

        # ---------- التنبيهات ----------
        "notifications": {
            "enabled": True,
            "tray_toast": True,
            "show_in_app": True,
            "warning_sound": False,
        },

        # ---------- المظهر والتشغيل ----------
        "appearance": {
            "language": "ar",
            "theme": "dark",
            "compact_mode": False,
        },
        "startup": {
            "run_with_windows": False,
            "start_minimized": False,
            "minimize_to_tray": True,
            "minimize_to_tray_on_close": True,
        },
        "shortcuts": {
            "desktop_shortcut": False,
            "start_menu_shortcut": False,
            "install_dir": "",
        },

        # ---------- المستخدمون ----------
        "users": [],
        "feature_flags": {
            "sfc_dism_repair": {"enabled": True, "tier": "free"},
            "advanced_process_control": {"enabled": True, "tier": "free"},
            "restore_point": {"enabled": True, "tier": "free"},
            "scheduled_maintenance": {"enabled": True, "tier": "free"},
        },
        "donate_url": "",
        "donate_message": "إذا أعجبك التطبيق، بإمكانك دعم تطويره مستقبلاً.",
    }

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or default_config_path()
        self.defaults = copy.deepcopy(self.DEFAULTS)
        self.settings = self.load()

    # ------------------------------------------------------------------
    # قراءة / كتابة
    # ------------------------------------------------------------------
    def load(self) -> dict:
        if not os.path.exists(self.config_path):
            data = copy.deepcopy(self.defaults)
            self.settings = data
            self._write_to_disk(data)
            return data

        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if not isinstance(loaded, dict):
                raise ValueError("config.json must contain a JSON object")
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError) as exc:
            logger.error("Failed to read config.json (%s); backing it up and restoring defaults.", exc)
            self._quarantine_corrupt_file()
            data = copy.deepcopy(self.defaults)
            self._write_to_disk(data)
            return data

        loaded = self._migrate(loaded)
        merged = deep_merge(self.defaults, loaded)
        merged["schema_version"] = self.DEFAULTS["schema_version"]
        merged = self.validate(merged)
        return merged

    def _migrate(self, loaded: dict) -> dict:
        """ترقية إعدادات النسخ القديمة إلى البنية الحالية دون فقدان أي قيمة."""
        data = copy.deepcopy(loaded)
        schema = int(data.get("schema_version", 1) or 1)

        if schema < 2:
            logger.info("Upgrading config schema from v%s to v2.", schema)
            # في النسخة القديمة كان تطبيق الصور ضمن قائمة الإنهاء الإجباري —
            # ننقله إلى قائمة الحماية (طلب صريح من صاحب المشروع: لا نلمس تطبيق الصور).
            kill_list = [str(x) for x in (data.get("force_kill_list") or [])]
            lowered = {x.lower() for x in kill_list}
            if "microsoft.photos.exe" in lowered:
                kill_list = [x for x in kill_list if x.lower() != "microsoft.photos.exe"]
                protected = list(data.get("process_exclusions") or [])
                if not any(p.lower() == "microsoft.photos.exe" for p in protected):
                    protected.append("Microsoft.Photos.exe")
                data["process_exclusions"] = protected
            data["force_kill_list"] = kill_list
            data.setdefault("schema_version", 2)
        return data

    def _quarantine_corrupt_file(self) -> None:
        try:
            backup_name = self.config_path + ".corrupt.bak"
            shutil.copy2(self.config_path, backup_name)
            logger.warning("Corrupt config backed up to %s", backup_name)
        except OSError as exc:
            logger.error("Could not back up corrupt config: %s", exc)

    def backup_now(self) -> bool:
        """حفظ نسخة احتياطية يدوية/تلقائية من الملف الحالي (config.json.bak)."""
        try:
            if os.path.exists(self.config_path):
                shutil.copy2(self.config_path, self.config_path + ".bak")
            return True
        except OSError as exc:
            logger.debug("Config backup failed: %s", exc)
            return False

    def restore_backup(self) -> bool:
        """استعادة الإعدادات من النسخة الاحتياطية إن وُجدت."""
        backup = self.config_path + ".bak"
        if not os.path.exists(backup):
            return False
        try:
            shutil.copy2(backup, self.config_path)
            self.settings = self.load()
            logger.info("Settings restored from backup.")
            return True
        except OSError as exc:
            logger.error("Could not restore config backup: %s", exc)
            return False

    def _write_to_disk(self, data: dict) -> bool:
        directory = os.path.dirname(os.path.abspath(self.config_path)) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            if os.path.exists(self.config_path):
                try:
                    shutil.copy2(self.config_path, self.config_path + ".bak")
                except OSError:
                    pass
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".config_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=4, ensure_ascii=False)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, self.config_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
            return True
        except OSError as exc:
            logger.error("Failed to save config.json: %s", exc)
            return False

    # ------------------------------------------------------------------
    def save(self, data: dict | None = None, merge: bool = True) -> bool:
        """
        حفظ الإعدادات.
        merge=True (افتراضي): دمج عميق مع الحالي — لا يُفقد أي مفتاح غير مرسل.
        merge=False: استبدال كامل (لكن مع القيم الافتراضية الناقصة).
        """
        if data:
            if merge:
                self.settings = deep_merge(self.settings, data)
            else:
                self.settings = deep_merge(self.defaults, data)
        self.settings = self.validate(self.settings)
        return self._write_to_disk(self.settings)

    def get(self, key: str, default=None):
        if key in self.settings:
            return self.settings[key]
        return self.defaults.get(key, default)

    def section(self, key: str) -> dict:
        """جلب قسم كامل (dict) مع ضمان أنه قاموس حتى لو تلف الملف."""
        value = self.get(key)
        return value if isinstance(value, dict) else {}

    def set(self, key: str, value, persist: bool = True) -> bool:
        self.settings[key] = value
        if persist:
            return self._write_to_disk(self.settings)
        return True

    def reset_section(self, key: str) -> bool:
        """إرجاع قسم معيّن لقيمه الافتراضية."""
        if key in self.defaults:
            self.settings[key] = copy.deepcopy(self.defaults[key])
            return self.save()
        return False

    # ------------------------------------------------------------------
    def validate(self, data: dict) -> dict:
        """تصحيح القيم غير المنطقية (نطاقات رقمية، أنواع) قبل الحفظ."""
        result = copy.deepcopy(data)

        def _clamp(value, low, high, fallback):
            try:
                value = int(value)
            except (TypeError, ValueError):
                return fallback
            return max(low, min(high, value))

        monitoring = result.get("monitoring")
        if isinstance(monitoring, dict):
            monitoring["interval_sec"] = _clamp(monitoring.get("interval_sec"), 1, 60, 2)
            monitoring["history_seconds"] = _clamp(monitoring.get("history_seconds"), 60, 3600, 300)
            monitoring["top_processes"] = _clamp(monitoring.get("top_processes"), 3, 50, 8)
            thresholds = monitoring.get("thresholds")
            if isinstance(thresholds, dict):
                for key, fallback in (("cpu_percent", 90), ("ram_percent", 90), ("disk_percent", 90)):
                    thresholds[key] = _clamp(thresholds.get(key), 10, 100, fallback)
                thresholds["sustained_seconds"] = _clamp(thresholds.get("sustained_seconds"), 3, 600, 15)

        health = result.get("health")
        if isinstance(health, dict):
            health["check_interval_min"] = _clamp(health.get("check_interval_min"), 5, 240, 30)
            health["low_disk_gb"] = _clamp(health.get("low_disk_gb"), 1, 100, 5)
            health["crash_events_per_scan"] = _clamp(health.get("crash_events_per_scan"), 5, 200, 20)

        for list_key in ("process_exclusions", "protected_apps", "force_kill_list", "service_exclusions"):
            value = result.get(list_key)
            if value is None:
                result[list_key] = []
            elif not isinstance(value, list):
                result[list_key] = [str(value)]
            else:
                cleaned = []
                for item in value:
                    text = str(item).strip()
                    if text and text not in cleaned:
                        cleaned.append(text)
                result[list_key] = cleaned

        if isinstance(result.get("appearance"), dict):
            lang = result["appearance"].get("language")
            result["appearance"]["language"] = lang if lang in ("ar", "en") else "ar"

        return result

    # ------------------------------------------------------------------
    # مساعدات الاستثناءات (تُستخدم من الواجهة ومدير الحماية)
    # ------------------------------------------------------------------
    def add_process_exclusion(self, name: str) -> bool:
        name = (name or "").strip()
        if not name:
            return False
        exclusions = list(self.get("process_exclusions") or [])
        if not any(x.lower() == name.lower() for x in exclusions):
            exclusions.append(name)
            return self.set("process_exclusions", exclusions)
        return True

    def remove_process_exclusion(self, name: str) -> bool:
        exclusions = [x for x in (self.get("process_exclusions") or []) if x.lower() != (name or "").lower()]
        return self.set("process_exclusions", exclusions)

    def add_protected_app(self, name: str) -> bool:
        name = (name or "").strip()
        if not name:
            return False
        apps = list(self.get("protected_apps") or [])
        if not any(x.lower() == name.lower() for x in apps):
            apps.append(name)
        # التطبيقات المحمية تُعامل كاستثناءات أيضًا (طبقة ثانية من الحماية)
        exclusions = list(self.get("process_exclusions") or [])
        if not any(x.lower() == name.lower() for x in exclusions):
            exclusions.append(name)
        return self.set("protected_apps", apps) and self.set("process_exclusions", exclusions)

    def remove_protected_app(self, name: str) -> bool:
        apps = [x for x in (self.get("protected_apps") or []) if x.lower() != (name or "").lower()]
        return self.set("protected_apps", apps)


__all__ = ["SettingsManager", "deep_merge"]
