import ctypes
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


class RepairResult:
    """نتيجة موحّدة لأي عملية إصلاح، عشان الواجهة تتعامل معها بشكل ثابت."""

    def __init__(self, success: bool, message: str, details: str = ""):
        self.success = success
        self.message = message
        self.details = details

    def __repr__(self):
        return f"RepairResult(success={self.success}, message={self.message!r})"


class SystemRepair:
    """
    عمليات إصلاح النظام. كل عملية:
    - تتحقق من صلاحيات المدير قبل التنفيذ وترجع رسالة واضحة لو غير متوفرة
      (بدل ما تفشل بصمت أو ترمي استثناء غير مفهوم للمستخدم).
    - تستخدم subprocess بدون shell=True قدر الإمكان (قائمة أوامر صريحة)
      لتقليل مخاطر حقن الأوامر (command injection)، حتى لو الأوامر هنا
      ثابتة وما تقبل مدخلات من المستخدم أصلاً.
    - محاطة بمعالجة استثناءات شاملة فما توقف التطبيق تحت أي ظرف.
    """

    def __init__(self, settings_manager):
        self.settings = settings_manager

    # ------------------------------------------------------------------
    def _require_admin(self, action_name: str) -> RepairResult | None:
        if not is_admin():
            msg = f"{action_name} يتطلب صلاحيات مدير النظام. شغّل البرنامج كـ Administrator."
            logger.warning(msg)
            return RepairResult(False, msg)
        return None

    def _run(self, cmd_list, timeout=1800):
        try:
            result = subprocess.run(
                cmd_list, capture_output=True, text=True, timeout=timeout, shell=False
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return -1, "", "Command not found on this system."
        except subprocess.TimeoutExpired:
            return -1, "", "Operation timed out."
        except OSError as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    def create_restore_point(self, description: str = None) -> RepairResult:
        """ينشئ نقطة استعادة نظام (System Restore) قبل أي عملية إصلاح خطرة."""
        guard = self._require_admin("إنشاء نقطة استعادة")
        if guard:
            return guard

        desc_template = description or self.settings.get("restore_point_description")
        desc = desc_template.format(date=datetime.now().strftime("%Y-%m-%d %H:%M"))
        # نستخدم PowerShell's Checkpoint-Computer لأنه أوثق من WMI مباشرة
        # ولا يتطلب اسم/مكتبة wmi إضافية لهذه العملية بالذات.
        ps_cmd = (
            f"Checkpoint-Computer -Description '{desc}' "
            f"-RestorePointType 'MODIFY_SETTINGS'"
        )
        code, out, err = self._run(["powershell", "-NoProfile", "-Command", ps_cmd])

        if code == 0:
            logger.info(f"Restore point created: {desc}")
            return RepairResult(True, "تم إنشاء نقطة استعادة بنجاح.", out)

        # سبب شائع للفشل: System Restore معطّل على القرص، أو تم إنشاء نقطة
        # قبل أقل من 24 ساعة (ويندوز يمنع التكرار بهذا الوقت افتراضيًا).
        logger.error(f"Restore point failed: {err or out}")
        return RepairResult(
            False,
            "تعذر إنشاء نقطة استعادة. تأكد أن System Restore مفعّل لهذا القرص "
            "(Control Panel > System Protection)، أو أنه لم يمر وقت قصير جدًا منذ آخر نقطة.",
            err or out,
        )

    def run_sfc(self) -> RepairResult:
        """فحص وإصلاح ملفات النظام التالفة (System File Checker)."""
        guard = self._require_admin("فحص ملفات النظام (SFC)")
        if guard:
            return guard

        logger.info("Running SFC /scannow (this can take several minutes)...")
        code, out, err = self._run(["sfc", "/scannow"], timeout=1800)

        if code == 0:
            return RepairResult(True, "SFC اكتمل: لم يتم العثور على انتهاكات أو تم إصلاحها.", out)
        return RepairResult(False, "SFC اكتمل مع مشاكل — راجع التفاصيل.", out or err)

    def run_dism(self) -> RepairResult:
        """إصلاح صورة نظام ويندوز (DISM RestoreHealth)."""
        guard = self._require_admin("إصلاح صورة النظام (DISM)")
        if guard:
            return guard

        logger.info("Running DISM /RestoreHealth (this can take a while and needs internet)...")
        code, out, err = self._run(
            ["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"], timeout=2400
        )

        if code == 0:
            return RepairResult(True, "DISM اكتمل بنجاح.", out)
        return RepairResult(False, "DISM واجه مشكلة — راجع التفاصيل.", out or err)

    def flush_dns(self) -> RepairResult:
        """تفريغ ذاكرة DNS المؤقتة - يحل مشاكل شائعة بالاتصال بالمواقع."""
        code, out, err = self._run(["ipconfig", "/flushdns"], timeout=30)
        if code == 0:
            return RepairResult(True, "تم تفريغ ذاكرة DNS المؤقتة.", out)
        return RepairResult(False, "تعذر تفريغ ذاكرة DNS.", err or out)

    def scan_disk(self, drive: str = "C:") -> RepairResult:
        """
        فحص القرص للأخطاء بدون تعطيل (read-only scan عبر /scan)، على عكس
        /f أو /r اللي تحتاج قفل القرص وربما إعادة تشغيل — هذا آمن للتشغيل
        بأي وقت بدون مقاطعة عمل المستخدم.
        """
        drive = drive.rstrip("\\") if drive else "C:"
        code, out, err = self._run(["chkdsk", drive, "/scan"], timeout=1800)
        # chkdsk يرجع رموز مختلفة حتى لو النتيجة سليمة، فنعتمد على النص
        combined = (out or "") + (err or "")
        found_issues = "found problems" in combined.lower() or "found errors" in combined.lower()
        if found_issues:
            return RepairResult(
                False,
                f"تم العثور على مشاكل بالقرص {drive}. شغّل 'chkdsk {drive} /f' من "
                "موجّه أوامر بصلاحيات مدير (سيتطلب إعادة تشغيل).",
                combined,
            )
        return RepairResult(True, f"لم يتم العثور على مشاكل بالقرص {drive}.", combined)
