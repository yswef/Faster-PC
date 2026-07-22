import os
import shutil
import logging

logger = logging.getLogger(__name__)


class SystemCleaner:
    """
    عمليات تنظيف آمنة: كل عملية حذف تتحقق أولاً إن المسار الحقيقي (بعد حل أي
    روابط رمزية) لسا داخل المجلد المستهدف قبل ما تحذف — هذا يمنع هجوم كلاسيكي
    حيث يوضع رابط رمزي (symlink) داخل مجلد Temp يشاور على ملف/مجلد حساس خارج
    Temp، فيصير الحذف يطال شيء ما كان مقصود (symlink attack / path escape).
    """

    def __init__(self, settings_manager):
        self.settings = settings_manager

    # ------------------------------------------------------------------
    def _is_safe_to_delete(self, base_dir: str, target_path: str) -> bool:
        try:
            real_base = os.path.realpath(base_dir)
            real_target = os.path.realpath(target_path)
            return os.path.commonpath([real_base, real_target]) == real_base
        except (ValueError, OSError):
            return False

    def _delete_item(self, item_path: str, base_dir: str, test_mode: bool) -> bool:
        """يحذف ملف/مجلد واحد بأمان. يرجع True لو نجح (أو محاكاة نجاح بوضع تجريبي)."""
        if os.path.islink(item_path):
            # لا نتبع الروابط الرمزية إطلاقًا - نحذف الرابط نفسه فقط إن كان
            # داخل المجلد المستهدف، وما نلمس الوجهة اللي يشاور عليها.
            if not self._is_safe_to_delete(base_dir, item_path):
                logger.warning(f"Skipped suspicious symlink outside target dir: {item_path}")
                return False
            if test_mode:
                logger.info(f"[TEST MODE] Would remove symlink: {item_path}")
                return True
            try:
                os.unlink(item_path)
                return True
            except OSError as e:
                logger.debug(f"Could not remove symlink {item_path}: {e}")
                return False

        if not self._is_safe_to_delete(base_dir, item_path):
            logger.warning(f"Skipped path outside target dir (possible escape): {item_path}")
            return False

        if test_mode:
            logger.info(f"[TEST MODE] Would remove: {item_path}")
            return True

        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=False)
            return True
        except PermissionError:
            logger.debug(f"Permission denied, skipped: {item_path}")
            return False
        except FileNotFoundError:
            return False
        except OSError as e:
            logger.debug(f"Could not remove {item_path}: {e}")
            return False

    # ------------------------------------------------------------------
    def clean_temp_files(self, include_temp=False):
        """
        تنظيف الملفات المؤقتة.
        include_temp=True يجب تمريره من الواجهة فقط بعد موافقة صريحة من
        المستخدم، لأنه يشمل مجلد %TEMP% الشخصي.
        """
        test_mode = bool(self.settings.get("test_mode"))
        temp_paths = [os.environ.get("TEMP"), r"C:\Windows\Temp"]

        if not include_temp:
            user_temp = os.environ.get("TEMP")
            temp_paths = [p for p in temp_paths if p != user_temp]

        removed, skipped = 0, 0
        for path in temp_paths:
            if not path or not os.path.exists(path):
                continue
            try:
                entries = os.listdir(path)
            except (PermissionError, OSError) as e:
                logger.warning(f"Could not list {path}: {e}")
                continue

            for item in entries:
                item_path = os.path.join(path, item)
                if self._delete_item(item_path, path, test_mode):
                    removed += 1
                else:
                    skipped += 1

        logger.info(f"Temp cleanup done: {removed} removed, {skipped} skipped/locked.")
        return {"removed": removed, "skipped": skipped}

    def clean_old_updates(self):
        """حذف ملفات التحديثات القديمة (SoftwareDistribution\\Download). يتطلب صلاحيات مدير."""
        test_mode = bool(self.settings.get("test_mode"))
        update_path = r"C:\Windows\SoftwareDistribution\Download"

        if not os.path.exists(update_path):
            logger.info("No Windows Update cache found.")
            return {"removed": 0, "skipped": 0}

        if test_mode:
            logger.info(f"[TEST MODE] Would clear: {update_path}")
            return {"removed": 0, "skipped": 0}

        try:
            shutil.rmtree(update_path, ignore_errors=False)
            os.makedirs(update_path, exist_ok=True)
            logger.info("Windows Update cache cleared.")
            return {"removed": 1, "skipped": 0}
        except PermissionError:
            logger.error("Permission denied clearing Windows Update cache. Run as Administrator.")
            return {"removed": 0, "skipped": 1}
        except OSError as e:
            logger.error(f"Failed to clear Windows Update cache: {e}")
            return {"removed": 0, "skipped": 1}

    def clean_recycle_bin(self):
        """إفراغ سلة المحذوفات لكل الأقراص. لا يمس أي بيانات خارجها."""
        test_mode = bool(self.settings.get("test_mode"))
        if test_mode:
            logger.info("[TEST MODE] Would empty the Recycle Bin.")
            return True
        try:
            import winshell  # type: ignore

            winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=True)
            logger.info("Recycle Bin emptied.")
            return True
        except ImportError:
            # winshell اختياري؛ بديل عبر PowerShell إذا غير متوفر
            try:
                import subprocess

                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, text=True, timeout=30,
                )
                logger.info("Recycle Bin emptied via PowerShell.")
                return True
            except Exception as e:
                logger.error(f"Could not empty Recycle Bin: {e}")
                return False
        except Exception as e:
            logger.error(f"Could not empty Recycle Bin: {e}")
            return False

    def clean_browser_cache(self, browser_local_appdata_folder: str):
        """
        تنظيف ملفات الـ Cache فقط (ليس Cookies أو Login Data أو أي بيانات
        اعتماد) لمتصفح Chromium-based، بمسار يحدده المستخدم صراحة من الواجهة.
        """
        test_mode = bool(self.settings.get("test_mode"))
        cache_dir = os.path.join(browser_local_appdata_folder, "Default", "Cache")
        if not os.path.isdir(cache_dir):
            logger.info("No browser cache folder found at the given path.")
            return {"removed": 0, "skipped": 0}

        removed, skipped = 0, 0
        try:
            for item in os.listdir(cache_dir):
                item_path = os.path.join(cache_dir, item)
                if self._delete_item(item_path, cache_dir, test_mode):
                    removed += 1
                else:
                    skipped += 1
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not list browser cache dir: {e}")

        logger.info(f"Browser cache cleanup: {removed} removed, {skipped} skipped.")
        return {"removed": removed, "skipped": skipped}
