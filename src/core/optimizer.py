import logging
import subprocess
import winreg
import psutil

logger = logging.getLogger(__name__)

# الحد الأدنى المطلق اللي ويندوز يحتاجه حرفيًا عشان يفضل شغال. هذي مو قائمة
# "أمان" - هذي عمليات لو انقتلت، النظام يسوي Blue Screen أو تسجيل خروج قسري
# فورًا بغض النظر عن أي إعداد. أي عملية ثانية (حتى svchost أو explorer)
# قابلة للإغلاق عادي حسب إعداداتك.
_BOOT_CRITICAL = {
    "system", "system idle process", "registry",
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "smss.exe",
}


class SystemOptimizer:
    def __init__(self, settings_manager):
        self.settings = settings_manager

    # ------------------------------------------------------------------
    # التحكم بالعمليات
    # ------------------------------------------------------------------
    def kill_unwanted_processes(self, dry_run=None):
        """ينهي فقط العمليات المدرجة صراحة بـ force_kill_list (مطابقة اسم دقيقة)."""
        dry_run = self.settings.get("test_mode") if dry_run is None else dry_run
        force_list = {f.lower() for f in (self.settings.get("force_kill_list") or [])}
        return self._terminate_matching(
            should_kill=lambda name: name in force_list and name not in _BOOT_CRITICAL,
            dry_run=dry_run,
        )

    def kill_all_except_excluded(self, dry_run=None, own_pid=None):
        """
        الزر الرئيسي: ينهي كل العمليات الجارية ما عدا:
        1) العمليات المدرجة بـ process_exclusions بالإعدادات (هذا بالضبط
           سبب وجود هذا الإعداد من الأصل).
        2) المجموعة الحرجة لإقلاع ويندوز (_BOOT_CRITICAL) - غير قابلة
           للتعديل من الإعدادات لأن قتلها يعطّل النظام فورًا لا محالة.
        3) عملية Faster PC نفسها (own_pid) عشان ما يقفل نفسه بنفسه.
        """
        dry_run = self.settings.get("test_mode") if dry_run is None else dry_run
        exclusions = {e.lower() for e in (self.settings.get("process_exclusions") or [])}

        def should_kill(name, pid):
            if name in _BOOT_CRITICAL:
                return False
            if name in exclusions:
                return False
            if own_pid is not None and pid == own_pid:
                return False
            return True

        return self._terminate_matching(should_kill=should_kill, dry_run=dry_run, pass_pid=True)

    def _terminate_matching(self, should_kill, dry_run, pass_pid=False):
        killed, failed = [], []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").strip()
                if not name:
                    continue
                name_lower = name.lower()
                pid = proc.info["pid"]

                match = should_kill(name_lower, pid) if pass_pid else should_kill(name_lower)
                if not match:
                    continue

                if dry_run:
                    logger.info(f"[TEST MODE] Would terminate: {name} (PID {pid})")
                    killed.append(name)
                    continue

                p = psutil.Process(pid)
                p.terminate()
                try:
                    p.wait(timeout=3)
                except psutil.TimeoutExpired:
                    p.kill()
                logger.info(f"Terminated: {name} (PID {pid})")
                killed.append(name)

            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                failed.append(proc.pid)
            except Exception as e:
                logger.debug(f"Unexpected error handling process {proc.pid}: {e}")
                failed.append(proc.pid)

        logger.info(f"Process sweep done: {len(killed)} terminated, {len(failed)} failed/denied.")
        return {"killed": killed, "failed": failed}

    def list_high_resource_processes(self, top_n=10):
        results = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mem = proc.info["memory_info"]
                if mem is None:
                    continue
                results.append({
                    "pid": proc.info["pid"],
                    "name": proc.info.get("name") or "Unknown",
                    "memory_mb": round(mem.rss / (1024 * 1024), 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return sorted(results, key=lambda p: p["memory_mb"], reverse=True)[:top_n]

    # ------------------------------------------------------------------
    # إدارة الخدمات
    # ------------------------------------------------------------------
    KNOWN_HEAVY_SERVICES = {
        "SysMain": "تحميل مسبق للتطبيقات بالذاكرة لتسريع الفتح؛ يزيد الحمل على القرص/الذاكرة خصوصًا على HDD.",
        "WSearch": "فهرسة بحث ويندوز؛ تستهلك CPU وقراءة/كتابة قرص أثناء الفهرسة.",
        "DiagTrack": "تتبع بيانات تشخيصية وترسلها لمايكروسوفت.",
        "MapsBroker": "مدير الخرائط دون اتصال؛ غير مطلوب إلا لتطبيق Maps.",
        "Fax": "خدمة الفاكس؛ نادرًا ما تُستخدم بالأجهزة الحديثة.",
        "WMPNetworkSvc": "مشاركة شبكة مشغل الوسائط؛ مطلوبة فقط للبث لأجهزة أخرى.",
        "TabletInputService": "لوحة اللمس/الكتابة اليدوية؛ غير مطلوبة بجهاز بدون شاشة لمس.",
        "PhoneSvc": "خدمة تكامل هاتفك مع تطبيق Your Phone.",
        "WerSvc": "تقارير أخطاء ويندوز؛ ترسل تقارير الأعطال لمايكروسوفت.",
        "RemoteRegistry": "تعديل الريجستري عن بعد؛ نادرًا ما يُستخدم بجهاز منزلي.",
        "PrintNotify": "إشعارات الطباعة؛ غير مطلوبة بدون طابعة.",
    }

    def list_services_status(self):
        results = []
        try:
            for name, desc in self.KNOWN_HEAVY_SERVICES.items():
                try:
                    svc = psutil.win_service_get(name)
                    info = svc.as_dict()
                    results.append({
                        "name": name,
                        "display_name": info.get("display_name", name),
                        "status": info.get("status", "unknown"),
                        "description": desc,
                    })
                except psutil.NoSuchProcess:
                    continue
        except AttributeError:
            logger.warning("win_service_get غير متوفر (يعمل فقط على ويندوز).")
        return results

    def set_service_state(self, service_name: str, enabled: bool) -> bool:
        protected = {s.lower() for s in (self.settings.get("service_exclusions") or [])}
        if service_name.lower() in protected:
            logger.warning(f"Refused to change protected service: {service_name}")
            return False

        dry_run = bool(self.settings.get("test_mode"))
        action = "تشغيل" if enabled else "إيقاف"
        if dry_run:
            logger.info(f"[TEST MODE] Would {action} service: {service_name}")
            return True

        try:
            if not enabled:
                subprocess.run(["sc", "stop", service_name], capture_output=True, text=True, timeout=20)
                code = subprocess.run(
                    ["sc", "config", service_name, "start=", "disabled"],
                    capture_output=True, text=True, timeout=20,
                ).returncode
            else:
                subprocess.run(
                    ["sc", "config", service_name, "start=", "auto"],
                    capture_output=True, text=True, timeout=20,
                )
                code = subprocess.run(
                    ["sc", "start", service_name], capture_output=True, text=True, timeout=20
                ).returncode

            logger.info(f"{action} الخدمة {service_name} (exit code {code}).")
            return code == 0
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to change service {service_name}: {e}")
            return False

    # ------------------------------------------------------------------
    # برامج بدء التشغيل
    # ------------------------------------------------------------------
    _STARTUP_KEYS = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ]
    _DISABLED_PREFIX = "_disabled_by_fasterpc_"

    def list_startup_items(self):
        items = []
        for hive, subkey in self._STARTUP_KEYS:
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            items.append({
                                "name": name,
                                "command": value,
                                "hive": "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM",
                                "disabled": name.startswith(self._DISABLED_PREFIX),
                            })
                            i += 1
                        except OSError:
                            break
            except FileNotFoundError:
                continue
            except PermissionError:
                logger.warning("Permission denied reading startup registry key (try Administrator).")
                continue
        return items

    def set_startup_item_enabled(self, name: str, hive_name: str, enabled: bool) -> bool:
        hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
        dry_run = bool(self.settings.get("test_mode"))

        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                if not enabled and not name.startswith(self._DISABLED_PREFIX):
                    value, vtype = winreg.QueryValueEx(key, name)
                    new_name = self._DISABLED_PREFIX + name
                    if dry_run:
                        logger.info(f"[TEST MODE] Would disable startup item: {name}")
                        return True
                    winreg.SetValueEx(key, new_name, 0, vtype, value)
                    winreg.DeleteValue(key, name)
                    logger.info(f"Disabled startup item: {name}")
                    return True

                if enabled and name.startswith(self._DISABLED_PREFIX):
                    value, vtype = winreg.QueryValueEx(key, name)
                    original_name = name[len(self._DISABLED_PREFIX):]
                    if dry_run:
                        logger.info(f"[TEST MODE] Would re-enable startup item: {original_name}")
                        return True
                    winreg.SetValueEx(key, original_name, 0, vtype, value)
                    winreg.DeleteValue(key, name)
                    logger.info(f"Re-enabled startup item: {original_name}")
                    return True

            return False
        except (FileNotFoundError, OSError, PermissionError) as e:
            logger.error(f"Could not change startup item {name}: {e}")
            return False
