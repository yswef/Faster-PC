"""
التنظيف الآمن — ملفات مؤقتة، سلة محذوفات، مخلفات تحديثات ويندوز، تقارير أعطال.

مبادئ غير قابلة للتفاوض في هذا الملف:
- كل حذف يتحقق أن المسار الحقيقي (بعد حل الروابط الرمزية) داخل المجلد المستهدف
  قبل الحذف — منع هجوم روابط رمزية (symlink attack) يخرج عن المجلد المصرّح به.
- لا يُحذف أي شيء من مجلدات المستخدم الشخصية غير المؤقتة، ولا ملفات الكوكيز أو
  كلمات المرور أو أي بيانات اعتماد أبدًا.
- كل عملية تُحسب (عدد المحذوف + الحجم المحرّر بالبايت) لعرض نتيجة حقيقية.
- أي عملية تحترم الوضع التجريبي (test_mode) في الوضعين.
"""

from __future__ import annotations

import logging
import os
import shutil

from src.core.results import ActionResult
from src.utils.paths import human_size
from src.utils.winapi import IS_WINDOWS, empty_recycle_bin, is_admin, recycle_bin_size, run_silent, windows_dir

logger = logging.getLogger(__name__)


class SystemCleaner:
    """عمليات تنظيف آمنة قابلة للتشغيل المتكرر بدون أي ضرر."""

    def __init__(self, settings_manager, notifier=None):
        self.settings = settings_manager
        self.notifier = notifier

    # ------------------------------------------------------------------
    # أدوات داخلية
    # ------------------------------------------------------------------
    def _test_mode(self) -> bool:
        return bool(self.settings.get("test_mode")) if self.settings else False

    @staticmethod
    def _is_safe_to_delete(base_dir: str, target_path: str) -> bool:
        try:
            real_base = os.path.realpath(base_dir)
            real_target = os.path.realpath(target_path)
            return os.path.commonpath([real_base, real_target]) == real_base
        except (ValueError, OSError):
            return False

    @staticmethod
    def _path_size(path: str) -> int:
        """حجم ملف/مجلد بالبايت (بدون اتباع الروابط الرمزية)."""
        try:
            if os.path.islink(path):
                return 0
            if os.path.isfile(path):
                return os.path.getsize(path)
            total = 0
            for root, _dirs, files in os.walk(path, onerror=lambda _e: None):
                for name in files:
                    try:
                        full = os.path.join(root, name)
                        if not os.path.islink(full):
                            total += os.path.getsize(full)
                    except OSError:
                        continue
            return total
        except OSError:
            return 0

    def _delete_item(self, item_path: str, base_dir: str, test_mode: bool, report: dict) -> bool:
        """حذف عنصر واحد مع كل حواجز الأمان. يحدّث عدّادات report."""
        if os.path.islink(item_path):
            if not self._is_safe_to_delete(base_dir, item_path):
                logger.warning("Skipped suspicious symlink outside target dir: %s", item_path)
                report["skipped"] += 1
                return False
            report["removed"] += 1
            if test_mode:
                return True
            try:
                os.unlink(item_path)
                return True
            except OSError:
                report["removed"] -= 1
                report["skipped"] += 1
                return False

        if not self._is_safe_to_delete(base_dir, item_path):
            logger.warning("Skipped path outside target dir (possible escape): %s", item_path)
            report["skipped"] += 1
            return False

        size = self._path_size(item_path)
        if test_mode:
            report["removed"] += 1
            report["freed"] += size
            return True

        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=False)
            else:
                report["skipped"] += 1
                return False
            report["removed"] += 1
            report["freed"] += size
            return True
        except PermissionError:
            report["skipped"] += 1
            report["locked"] += 1
            return False
        except FileNotFoundError:
            report["skipped"] += 1
            return False
        except OSError:
            report["skipped"] += 1
            return False

    def _clean_directory(self, path: str, test_mode: bool, report: dict, label: str) -> None:
        if not path or not os.path.isdir(path):
            return
        try:
            entries = os.listdir(path)
        except (PermissionError, OSError) as exc:
            logger.warning("Could not list %s (%s): %s", label, path, exc)
            return
        for item in entries:
            self._delete_item(os.path.join(path, item), path, test_mode, report)

    @staticmethod
    def _new_report() -> dict:
        return {"removed": 0, "skipped": 0, "freed": 0, "locked": 0}

    def _summarize(self, report: dict, label: str) -> ActionResult:
        message = (
            f"{label}: حُذف {report['removed']} عنصرًا "
            f"(وفّر {human_size(report['freed'])})، تُخطّي {report['skipped']}"
            + (f" منها {report['locked']} ملف مستخدم/مقفل" if report["locked"] else "")
            + "."
        )
        if self._test_mode():
            message = "[وضع المعاينة] " + message.replace("حُذف", "كان سيُحذف")
        success = report["removed"] > 0 or report["skipped"] == 0
        return ActionResult(success, message, data=dict(report))

    # ------------------------------------------------------------------
    # العمليات العامة
    # ------------------------------------------------------------------
    def temp_directories(self, include_user_temp: bool = False) -> list[tuple[str, str]]:
        """قائمة (المسار، الوصف) للمجلدات المؤقتة المستهدفة."""
        dirs: list[tuple[str, str]] = []
        if IS_WINDOWS:
            dirs.append((os.path.join(windows_dir(), "Temp"), "مجلد ويندوز المؤقت"))
        user_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if user_temp and include_user_temp:
            dirs.append((user_temp, "مجلد المستخدم المؤقت %TEMP%"))
        if not IS_WINDOWS:
            import tempfile

            dirs.append((tempfile.gettempdir(), "مجلد النظام المؤقت"))
        return dirs

    def clean_temp_files(self, include_temp: bool = False) -> ActionResult:
        """تنظيف الملفات المؤقتة (ويندوز دائمًا، والمستخدم فقط بموافقة صريحة)."""
        test_mode = self._test_mode()
        report = self._new_report()
        for path, label in self.temp_directories(include_temp):
            if self._test_mode():
                # في وضع المعاينة نحسب الحجم التقريبي بلا حذف
                try:
                    for item in os.listdir(path):
                        report["freed"] += self._path_size(os.path.join(path, item))
                        report["removed"] += 1
                except OSError:
                    continue
            else:
                self._clean_directory(path, test_mode, report, label)
        return self._summarize(report, "تنظيف الملفات المؤقتة")

    def clean_error_reports(self) -> ActionResult:
        """حذف ملفات تقارير أخطاء ويندوز (WER) المتراكمة للمستخدم الحالي."""
        test_mode = self._test_mode()
        report = self._new_report()
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        targets = [
            os.path.join(base, "Microsoft", "Windows", "WER"),
            os.path.join(base, "CrashDumps"),
        ]
        for path in targets:
            if os.path.isdir(path):
                self._clean_directory(path, test_mode, report, "تقارير الأعطال")
        return self._summarize(report, "تنظيف تقارير الأعطال")

    def clean_old_updates(self) -> ActionResult:
        """
        تفريغ مجلد تحديثات ويندوز المؤقت — بالطريقة الصحيحة:
        إيقاف خدمتي التحديثات، التفريغ، ثم إعادة تشغيلهما كما كانتا.
        """
        if not IS_WINDOWS:
            return ActionResult(False, "هذه العملية خاصة بويندوز.")
        if not is_admin():
            return ActionResult(False, "تفريغ مخلفات التحديثات يتطلب تشغيل البرنامج كمسؤول (Admin).")

        test_mode = self._test_mode()
        update_path = os.path.join(windows_dir(), "SoftwareDistribution", "Download")
        if not os.path.isdir(update_path):
            return ActionResult(True, "لا يوجد مجلد تحديثات قديم لتنظيفه.", data={"removed": 0})

        if test_mode:
            size = self._path_size(update_path)
            return ActionResult(
                True,
                f"[وضع المعاينة] كان سيتم تفريغ مخلفات التحديثات (حجمها نحو {human_size(size)}).",
                data={"removed": 0, "freed": size},
            )

        services = ["wuauserv", "bits"]
        logger.info("Stopping update services before clearing cache...")
        for name in services:
            run_silent(["sc", "stop", name], timeout=60)

        report = self._new_report()
        try:
            for item in os.listdir(update_path):
                self._delete_item(os.path.join(update_path, item), update_path, False, report)
        except OSError as exc:
            logger.warning("Could not clear update cache: %s", exc)

        for name in services:
            run_silent(["sc", "start", name], timeout=60)

        result = self._summarize(report, "تفريغ مخلفات تحديثات ويندوز")
        result.details = "أُعيد تشغيل خدمات التحديثات تلقائيًا بعد التفريغ."
        return result

    def clean_recycle_bin(self) -> ActionResult:
        """إفراغ سلة المحذوفات (مع معرفة حجمها قبل الإفراغ)."""
        if self._test_mode():
            size, items = recycle_bin_size()
            text = f" ({human_size(size)} / {items} عنصرًا)" if size else ""
            return ActionResult(True, f"[وضع المعاينة] كان سيتم إفراغ سلة المحذوفات{text}.")
        if not IS_WINDOWS:
            return ActionResult(False, "إفراغ سلة المحذوفات متاح على ويندوز فقط.")
        size, items = recycle_bin_size()
        if empty_recycle_bin():
            return ActionResult(
                True,
                f"تم إفراغ سلة المحذوفات (أُفرغ نحو {human_size(size)} / {items} عنصرًا).",
                data={"freed": size, "items": items},
            )
        return ActionResult(False, "تعذر إفراغ سلة المحذوفات.")

    def clean_browser_cache(self, browser_local_appdata_folder: str) -> ActionResult:
        """
        تنظيف مجلد الكاش لمتصفح مبني على Chromium — الكاش فقط، ولا يلمس
        الكوكيز أو كلمات المرور أو سجل التصفح أو أي بيانات اعتماد.
        """
        cache_dir = os.path.join(browser_local_appdata_folder, "Default", "Cache")
        if not os.path.isdir(cache_dir):
            return ActionResult(False, f"لم يُعثر على مجلد كاش المتصفح: {cache_dir}")
        report = self._new_report()
        self._clean_directory(cache_dir, self._test_mode(), report, "كاش المتصفح")
        return self._summarize(report, "تنظيف كاش المتصفح")

    def estimate_temp_size(self, include_temp: bool = False) -> int:
        """حجم المخلفات المؤقتة الحالي بالبايت (لعرضه قبل التنظيف)."""
        total = 0
        for path, _label in self.temp_directories(include_temp):
            if path and os.path.isdir(path):
                total += self._path_size(path)
        return total


__all__ = ["SystemCleaner"]
