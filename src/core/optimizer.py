"""
تحسين العمليات والخدمات وبرامج بدء التشغيل.

نقاط الأمان المهمة:
- لا يُنهى أي عملية إلا بعد فحصها في ProtectionManager (حماية ثلاثية الطبقات).
- حالة الخدمات تُقرأ من الريجستري مباشرة (Start type) — لا تحليل نصوص مترجمة.
- تعطيل برامج بدء التشغيل يتم بإعادة تسمية القيمة مع سجل تغييرات كامل، فالرجوع
  ممكن بنقرة واحدة من تبويب "سجل التغييرات".
- كل أمر خارجي يشتغل بصمت تام (بدون نوافذ cmd).
"""

from __future__ import annotations

import logging

import psutil

from src.core.exclusions import ProtectionManager
from src.core.results import ActionResult
from src.utils.registry import read_value, registry_available, winreg
from src.utils.winapi import IS_WINDOWS, is_admin, run_silent

logger = logging.getLogger(__name__)

_DISABLED_PREFIX = "_disabled_by_fasterpc_"
_STARTUP_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
]
_SERVICE_REG_PATH = r"SYSTEM\CurrentControlSet\Services\{name}"
_START_TYPES = {2: "تلقائي", 3: "يدوي", 4: "معطّل", 0: "تمهيدي", 1: "تمهيدي للنظام"}


class OptimizerService:
    """وصف خدمة ويندوز معروضة للمستخدم."""

    def __init__(self, name: str, description: str, impact: str, safe: bool = True):
        self.name = name
        self.description = description
        self.impact = impact
        self.safe = safe  # لو False، الإيقاف قد يؤثر على وظائف مهمة


class SystemOptimizer:
    """إدارة العمليات والخدمات وبرامج بدء التشغيل."""

    # خدمات معروفة بالاستهلاك المرتفع، مع بيان تأثيرها الحقيقي قبل الإيقاف.
    KNOWN_HEAVY_SERVICES: dict[str, OptimizerService] = {
        "SysMain": OptimizerService(
            "SysMain", "التحميل المسبق للتطبيقات في الذاكرة لتسريع فتحها.",
            "على الأقراص الصلبة القديمة يخفف الحمل؛ على SSD قد لا يقدم فائدة تُذكر.", True),
        "WSearch": OptimizerService(
            "WSearch", "فهرسة البحث في ويندوز (بحث قائمة ابدأ والملفات).",
            "إيقافه يزيل نتائج البحث في الملفات ويُسرّع الجهاز أثناء الفهرسة.", True),
        "DiagTrack": OptimizerService(
            "DiagTrack", "جمع بيانات التشخيص وإرسالها لمايكروسوفت.",
            "إيقافه يمنع إرسال تقارير الاتصال والاستخدام.", True),
        "MapsBroker": OptimizerService(
            "MapsBroker", "تنزيل وتحديث خرائط تطبيق الخرائط.",
            "غير مطلوب إلا إذا كنت تستخدم تطبيق الخرائط.", True),
        "Fax": OptimizerService("Fax", "خدمة الفاكس.", "نادرًا ما تُستخدم بالأجهزة الحديثة.", True),
        "WMPNetworkSvc": OptimizerService(
            "WMPNetworkSvc", "مشاركة مكتبة Windows Media Player عبر الشبكة.",
            "مطلوبة فقط للبث لأجهزة أخرى.", True),
        "TabletInputService": OptimizerService(
            "TabletInputService", "لوحة اللمس والكتابة اليدوية.",
            "غير مطلوبة على جهاز بدون شاشة لمس.", True),
        "PhoneSvc": OptimizerService("PhoneSvc", "تكامل الهاتف مع تطبيق 'هاتفي'.",
                                      "غير مطلوبة إذا لم تستخدم مزامنة الهاتف.", True),
        "WerSvc": OptimizerService("WerSvc", "تقارير أخطاء ويندوز.",
                                    "إيقافه يوقف إرسال تقارير الأعطال لمايكروسوفت.", True),
        "RemoteRegistry": OptimizerService("RemoteRegistry", "تعديل الريجستري عن بُعد.",
                                            "نادرًا ما يُستخدم بجهاز منزلي، وإيقافه مفيد أمنيًا.", True),
        "PrintNotify": OptimizerService("PrintNotify", "إشعارات الطباعة.",
                                         "غير مطلوب بدون طابعة.", True),
        "dmwappushservice": OptimizerService("dmwappushservice", "خدمة رسائل إدارة الأجهزة (WAP Push).",
                                             "مرتبطة بخدمة DiagTrack وغير مطلوبة لجهاز شخصي.", True),
        "RetailDemo": OptimizerService("RetailDemo", "وضع العرض التجاري للمتاجر.",
                                        "غير مطلوبة إطلاقًا بجهاز شخصي.", True),
    }

    def __init__(self, settings_manager, journal=None, notifier=None, own_pid: int | None = None):
        self.settings = settings_manager
        self.journal = journal
        self.notifier = notifier
        self.protection = ProtectionManager(settings_manager, own_pid)
        if journal is not None:
            journal.register_undo_handler("startup_item", self._undo_startup_item)
            journal.register_undo_handler("service_state", self._undo_service_state)
            journal.register_undo_handler("process_sweep", self._undo_process_sweep)

    # ------------------------------------------------------------------
    # أدوات
    # ------------------------------------------------------------------
    def _test_mode(self) -> bool:
        return bool(self.settings.get("test_mode")) if self.settings else False

    def _record(self, kind: str, description: str, data: dict) -> None:
        if self.journal is not None:
            self.journal.record(kind, description, data)

    # ------------------------------------------------------------------
    # إنهاء العمليات
    # ------------------------------------------------------------------
    def kill_unwanted_processes(self, dry_run: bool | None = None) -> ActionResult:
        """إنهاء العمليات المدرجة صراحة في قائمة force_kill_list فقط."""
        dry = self._test_mode() if dry_run is None else dry_run
        force_list = {str(x).strip().lower() for x in (self.settings.get("force_kill_list") or [])}

        killed, failed, protected = [], [], []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").strip()
                if not name or name.lower() not in force_list:
                    continue
                allowed, reason = self.protection.check_process(proc, name=name, pid=proc.info["pid"])
                if not allowed:
                    protected.append({"name": name, "reason": reason})
                    continue
                if dry:
                    killed.append({"name": name, "pid": proc.info["pid"]})
                    logger.info("[وضع المعاينة] كان سيُنهى: %s (PID %s)", name, proc.info["pid"])
                    continue
                self.terminate_process(proc, name)
                killed.append({"name": name, "pid": proc.info["pid"]})
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                failed.append(proc.pid)
            except Exception as exc:  # pragma: no cover
                logger.debug("Unexpected error on pid %s: %s", proc.pid, exc)
                failed.append(proc.pid)

        return self._sweep_result("قائمة الإنهاء المحددة", killed, failed, protected, dry)

    def kill_all_except_excluded(self, dry_run: bool | None = None) -> ActionResult:
        """
        إنهاء كل العمليات الجارية ما عدا:
        - المحمية دائمًا (نواة/إقلاع ويندوز) — غير قابلة للاستثناء.
        - استثناءاتك (process_exclusions + protected_apps).
        - البرنامج نفسه وكل عملية فرعية يشغّلها.
        """
        dry = self._test_mode() if dry_run is None else dry_run
        killed, failed, protected = [], [], []

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").strip()
                if not name:
                    continue
                allowed, reason = self.protection.check_process(proc, name=name, pid=proc.info["pid"])
                if not allowed:
                    protected.append({"name": name, "reason": reason})
                    continue
                if dry:
                    killed.append({"name": name, "pid": proc.info["pid"]})
                    continue
                self.terminate_process(proc, name)
                killed.append({"name": name, "pid": proc.info["pid"]})
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                failed.append(proc.pid)
            except Exception as exc:  # pragma: no cover
                logger.debug("Unexpected error on pid %s: %s", proc.pid, exc)
                failed.append(proc.pid)

        return self._sweep_result("إنهاء كل العمليات غير المستثناة", killed, failed, protected, dry)

    @staticmethod
    def terminate_process(proc: psutil.Process, name: str) -> None:
        """إنهاء عملية بأمان: terminate ثم kill لو ما استجابت خلال 3 ثوان."""
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()
        logger.info("أُنهيت العملية: %s (PID %s)", name, proc.pid)

    def _sweep_result(self, label: str, killed: list, failed: list, protected: list, dry: bool) -> ActionResult:
        protected_names = {}
        for item in protected:
            protected_names[item["name"]] = protected_names.get(item["name"], 0) + 1

        message = (
            f"{label}: أُنهي {len(killed)} عملية، تعذّر {len(failed)}، "
            f"حُميت {len(protected)} عملية."
        )
        if dry:
            message = f"[وضع المعاينة] {label}: كان سيُنهى {len(killed)} عملية، و{len(protected)} عملية محمية."
        details_lines = [f"محمية: {name} ×{count}" for name, count in sorted(protected_names.items())[:40]]
        return ActionResult(
            True,
            message,
            details="\n".join(details_lines),
            data={"killed": killed, "failed": failed, "protected": protected},
        )

    def _undo_process_sweep(self, entry: dict) -> tuple[bool, str]:
        return False, "إنهاء العمليات غير قابل للتراجع — البرامج المُنهية تحتاج إعادة تشغيل يدويًا."

    def list_high_resource_processes(self, top_n: int = 10) -> list[dict]:
        """أعلى العمليات استهلاكًا للذاكرة والمعالج (مع بيان إن كانت محمية)."""
        results = []
        for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                name = info.get("name") or "غير معروف"
                allowed, reason = self.protection.check_process(name=name, pid=info["pid"])
                results.append({
                    "pid": info["pid"],
                    "name": name,
                    "memory_mb": round((mem.rss if mem else 0) / (1024 ** 2), 1),
                    "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                    "protected": not allowed,
                    "protection_reason": reason,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        results.sort(key=lambda p: (p["cpu_percent"], p["memory_mb"]), reverse=True)
        return results[:top_n]

    # ------------------------------------------------------------------
    # الخدمات
    # ------------------------------------------------------------------
    def list_services_status(self) -> list[dict]:
        """حالة الخدمات المعروفة + نوع تشغيلها الحالي."""
        results = []
        for name, svc in sorted(self.KNOWN_HEAVY_SERVICES.items()):
            entry = {
                "name": name,
                "description": svc.description,
                "impact": svc.impact,
                "status": "غير معروفة",
                "start_type": "غير معروف",
                "protected": False,
            }
            try:
                service = psutil.win_service_get(name)
                info = service.as_dict()
                entry["status"] = info.get("status", "unknown")
                entry["display_name"] = info.get("display_name", name)
            except Exception:
                pass
            if registry_available():
                start = read_value(winreg.HKEY_LOCAL_MACHINE, _SERVICE_REG_PATH.format(name=name), "Start")
                if isinstance(start, int):
                    entry["start_type"] = _START_TYPES.get(start, str(start))
                elif start is None:
                    if entry["status"] == "غير معروفة":
                        continue  # الخدمة غير موجودة على هذا النظام أصلًا
            protected, reason = self.protection.is_service_protected(name)
            entry["protected"] = protected
            entry["protection_reason"] = reason
            results.append(entry)
        return results

    def set_service_state(self, service_name: str, enabled: bool) -> ActionResult:
        """إيقاف/تشغيل خدمة مع تسجيل حالتها السابقة للتراجع."""
        protected, reason = self.protection.is_service_protected(service_name)
        if protected:
            return ActionResult(False, f"رفضت العملية: {service_name} محمية ({reason}).")

        if self._test_mode():
            action = "تشغيل" if enabled else "إيقاف"
            return ActionResult(True, f"[وضع المعاينة] كان سيتم {action} الخدمة {service_name}.")
        if not IS_WINDOWS:
            return ActionResult(False, "إدارة الخدمات متاحة على ويندوز فقط.")
        if not is_admin():
            return ActionResult(False, f"إيقاف/تشغيل خدمة {service_name} يتطلب صلاحيات مدير.")

        previous_start = read_value(winreg.HKEY_LOCAL_MACHINE, _SERVICE_REG_PATH.format(name=service_name), "Start")
        was_running = False
        try:
            was_running = psutil.win_service_get(service_name).status() == "running"
        except Exception:
            pass

        action = "تشغيل" if enabled else "إيقاف"
        if enabled:
            run_silent(["sc", "config", service_name, "start=", "auto"], timeout=30)
            result = run_silent(["sc", "start", service_name], timeout=45)
            success = result.returncode in (0, 1056)  # 1056 = تعمل مسبقًا
        else:
            run_silent(["sc", "stop", service_name], timeout=60)
            result = run_silent(["sc", "config", service_name, "start=", "disabled"], timeout=30)
            success = result.ok

        if success:
            self._record(
                "service_state",
                f"{action} خدمة {service_name}",
                {"name": service_name, "was_running": was_running, "previous_start": previous_start},
            )
            return ActionResult(True, f"تم {action} الخدمة {service_name}.")
        return ActionResult(False, f"تعذر {action} الخدمة {service_name}.", details=result.output)

    def _undo_service_state(self, entry: dict) -> tuple[bool, str]:
        data = entry.get("data", {})
        name = data.get("name")
        if not name:
            return False, "بيانات التراجع ناقصة."
        previous = data.get("previous_start")
        if isinstance(previous, int):
            start_value = {2: "auto", 3: "demand", 4: "disabled"}.get(previous, "demand")
            run_silent(["sc", "config", name, "start=", start_value], timeout=30)
        if data.get("was_running"):
            run_silent(["sc", "start", name], timeout=45)
        return True, f"أُعيدت خدمة {name} لحالتها السابقة."

    # ------------------------------------------------------------------
    # برامج بدء التشغيل
    # ------------------------------------------------------------------
    def list_startup_items(self) -> list[dict]:
        items = []
        if not registry_available():
            return items
        for hive, subkey, hive_name in _STARTUP_KEYS:
            for name, value, _vtype in _enumerate_registry_values(hive, subkey):
                items.append({
                    "name": name,
                    "command": value,
                    "hive": hive_name,
                    "disabled": name.startswith(_DISABLED_PREFIX),
                    "original_name": name[len(_DISABLED_PREFIX):] if name.startswith(_DISABLED_PREFIX) else name,
                })
        return items

    def set_startup_item_enabled(self, name: str, hive_name: str, enabled: bool) -> ActionResult:
        if not registry_available():
            return ActionResult(False, "ريجستري ويندوز غير متوفر على هذا النظام.")
        hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
        dry = self._test_mode()

        if not enabled and name.startswith(_DISABLED_PREFIX):
            return ActionResult(True, f"العنصر {name} معطّل مسبقًا.")
        if enabled and not name.startswith(_DISABLED_PREFIX):
            return ActionResult(True, f"العنصر {name} مفعّل مسبقًا.")

        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                value, vtype = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return ActionResult(False, f"لم يُعثر على عنصر بدء التشغيل: {name}")
        except PermissionError:
            return ActionResult(False, f"صلاحيات غير كافية لتعديل {name} (يتطلب مدير).")
        except OSError as exc:
            return ActionResult(False, f"تعذر قراءة العنصر {name}: {exc}")

        if dry:
            action = "تفعيل" if enabled else "تعطيل"
            return ActionResult(True, f"[وضع المعاينة] كان سيتم {action} عنصر بدء التشغيل: {name}")

        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                if not enabled:
                    new_name = _DISABLED_PREFIX + name
                    winreg.SetValueEx(key, new_name, 0, vtype, value)
                    winreg.DeleteValue(key, name)
                    self._record(
                        "startup_item",
                        f"تعطيل برنامج بدء التشغيل: {name}",
                        {"name": new_name, "original": name, "hive": hive_name},
                    )
                    return ActionResult(True, f"تم تعطيل برنامج بدء التشغيل: {name}")
                original = name[len(_DISABLED_PREFIX):]
                winreg.SetValueEx(key, original, 0, vtype, value)
                winreg.DeleteValue(key, name)
                self._record(
                    "startup_item",
                    f"إعادة تفعيل برنامج بدء التشغيل: {original}",
                    {"name": original, "original": name, "hive": hive_name, "reenabled": True},
                )
                return ActionResult(True, f"تم إعادة تفعيل برنامج بدء التشغيل: {original}")
        except PermissionError:
            return ActionResult(False, f"صلاحيات غير كافية لتعديل {name} (يتطلب مدير).")
        except OSError as exc:
            return ActionResult(False, f"تعذر تعديل {name}: {exc}")

    def _undo_startup_item(self, entry: dict) -> tuple[bool, str]:
        """تراجع عن تعطيل/تفعيل برنامج بدء تشغيل."""
        if not registry_available():
            return False, "ريجستري ويندوز غير متوفر."
        data = entry.get("data", {})
        current_name = data.get("name")
        original_name = data.get("original")
        hive_name = data.get("hive", "HKCU")
        hive = winreg.HKEY_CURRENT_USER if hive_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                value, vtype = winreg.QueryValueEx(key, current_name)
                winreg.SetValueEx(key, original_name, 0, vtype, value)
                winreg.DeleteValue(key, current_name)
            return True, f"تم التراجع عن التغيير وإعادة {original_name}."
        except OSError as exc:
            return False, f"تعذر التراجع: {exc}"


def _enumerate_registry_values(hive, subkey: str) -> list[tuple[str, str, int]]:
    """قراءة كل قيم مفتاح Run (اسم، قيمة، نوع) بأمان."""
    items: list[tuple[str, str, int]] = []
    try:
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            index = 0
            while True:
                try:
                    name, value, vtype = winreg.EnumValue(key, index)
                    items.append((name, str(value), vtype))
                    index += 1
                except OSError:
                    break
    except FileNotFoundError:
        pass
    except PermissionError:
        logger.warning("صلاحيات غير كافية لقراءة برامج بدء التشغيل (%s).", subkey)
    except OSError as exc:
        logger.debug("Could not read %s: %s", subkey, exc)
    return items


__all__ = ["SystemOptimizer", "OptimizerService"]
