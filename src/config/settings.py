import json
import os
import shutil
import logging
import tempfile

logger = logging.getLogger(__name__)


class SettingsManager:
    """
    يدير تحميل/حفظ إعدادات التطبيق من config.json بشكل آمن:
    - كتابة ذرية (atomic write) لتفادي تلف الملف عند انقطاع الكهرباء/تعليق البرنامج.
    - نسخة احتياطية تلقائية للملف التالف بدل استبداله بصمت.
    - دمج الإعدادات الجديدة مع القديمة بدل الاستبدال الكامل (save يدعم partial update).
    """

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.defaults = {
            "process_exclusions": [
                "system", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
                "explorer.exe", "svchost.exe", "smss.exe", "python.exe", "pythonw.exe",
                "cmd.exe", "powershell.exe", "TextInputHost.exe",
                "WUDFHost.exe", "WmiPrvSE.exe", "OpenConsole.exe", "WindowsTerminal.exe",
                "fontdrvhost.exe", "RuntimeBroker.exe", "ShellExperienceHost.exe",
                "StartMenuExperienceHost.exe",
            ],
            "force_kill_list": [
                "pet.exe", "rsAppUI.exe", "Microsoft.Photos.exe", "Everything.exe",
                "BraveCrashHandler.exe", "BraveCrashHandler64.exe", "MicrosoftEdgeUpdate.exe",
            ],
            "test_mode": True,  # الوضع التجريبي: يسجل الإجراءات بدون تنفيذها فعليًا
            "restore_point_description": "Faster PC Restore Point - {date}",
            "service_exclusions": ["WinDefend", "EventLog"],
            "auto_clean_temp": False,
            # نظام المستخدمين: كل مستخدم = {"username", "salt", "password_hash", "role"}
            # role: "admin" | "user". يُنشأ أول حساب أدمين تلقائيًا عند أول تشغيل.
            "users": [],
            # بنية جاهزة لخطط مستقبلية (مجاني/مدفوع) - كل الميزات مفتوحة حاليًا للجميع
            "feature_flags": {
                "sfc_dism_repair": {"enabled": True, "tier": "free"},
                "advanced_process_control": {"enabled": True, "tier": "free"},
                "restore_point": {"enabled": True, "tier": "free"},
                "scheduled_maintenance": {"enabled": True, "tier": "free"},
            },
            "donate_url": "",
            "donate_message": "إذا أعجبك التطبيق، بإمكانك دعم تطويره مستقبلاً.",
        }
        self.settings = self.load()

    # ------------------------------------------------------------------
    def load(self):
        """تحميل الإعدادات من ملف JSON، أو إنشاء ملف افتراضي إذا لم يوجد."""
        if not os.path.exists(self.config_path):
            self.settings = dict(self.defaults)
            self._write_to_disk(self.settings)
            return self.settings

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.error(f"Failed to read config.json ({e}); backing it up and restoring defaults.")
            self._quarantine_corrupt_file()
            loaded = dict(self.defaults)
            self._write_to_disk(loaded)
            return loaded

        # دمج مع القيم الافتراضية: أي مفتاح جديد أضفناه بنسخة أحدث من
        # البرنامج يظهر تلقائيًا بدون ما يفقد المستخدم إعداداته الحالية.
        merged = dict(self.defaults)
        merged.update(loaded)
        return merged

    def _quarantine_corrupt_file(self):
        try:
            backup_name = self.config_path + ".corrupt.bak"
            shutil.copy2(self.config_path, backup_name)
            logger.warning(f"Corrupt config backed up to {backup_name}")
        except OSError as e:
            logger.error(f"Could not back up corrupt config: {e}")

    def _write_to_disk(self, data):
        """كتابة ذرية: تكتب لملف مؤقت ثم تستبدل الملف الأصلي دفعة واحدة،
        بحيث لا يتبقى ملف نصف مكتوب لو صار انقطاع أثناء الحفظ."""
        directory = os.path.dirname(os.path.abspath(self.config_path)) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".config_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                os.replace(tmp_path, self.config_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise
            return True
        except OSError as e:
            logger.error(f"Failed to save config.json: {e}")
            return False

    def save(self, data=None, merge=True):
        """
        حفظ الإعدادات إلى ملف JSON.
        merge=True (افتراضي): يدمج data مع الإعدادات الحالية (partial update)
        بدل استبدال كل الإعدادات — يمنع فقدان مفاتيح غير مرسلة.
        merge=False: استبدال كامل (استخدمها فقط لو متأكد إنك مرسل الكائن كامل).
        """
        if data:
            if merge:
                self.settings.update(data)
            else:
                self.settings = data
        return self._write_to_disk(self.settings)

    def get(self, key):
        """جلب قيمة إعداد معين."""
        return self.settings.get(key, self.defaults.get(key))

    def set(self, key, value, persist=True):
        """تحديث إعداد واحد وحفظه فورًا (اختياري)."""
        self.settings[key] = value
        if persist:
            return self._write_to_disk(self.settings)
        return True
