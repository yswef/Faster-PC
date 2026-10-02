"""
التثبيت والإعداد من داخل البرنامج:
- اختصارات سطح المكتب وقائمة ابدأ (بالأيقونة الصحيحة — اللي كانت ناقصة).
- تسجيل التشغيل التلقائي مع ويندوز.
- استثناءات Windows Defender (اختيارية، بموافقة المستخدم) لتقليل الإنذارات
  الكاذبة المعروفة ضد أي برنامج غير موقّع مبني بـ PyInstaller.
- إزالة كل ما سبق (رجوع نظيف).
"""

from __future__ import annotations

import logging
import os

from src.core.results import ActionResult
from src.utils.paths import executable_dir, resource_path, shortcuts_dir
from src.utils.winapi import (
    IS_WINDOWS,
    create_app_shortcut,
    is_admin,
    is_run_at_startup,
    remove_shortcut,
    run_powershell,
    set_run_at_startup,
)
from src.version import APP_NAME

logger = logging.getLogger(__name__)


def app_icon_path() -> str:
    """مسار أيقونة التطبيق (ico على ويندوز، png كبديل)."""
    ico = resource_path("assets/app_icon.ico")
    if os.path.exists(ico):
        return ico
    return resource_path("assets/icon_256.png")


class SystemInstaller:
    """مسؤول عن كل ما يتعلق بترسيخ البرنامج على الجهاز (وإزالته بأمان)."""

    def __init__(self, settings_manager=None, notifier=None):
        self.settings = settings_manager
        self.notifier = notifier

    # ------------------------------------------------------------------
    # الاختصارات
    # ------------------------------------------------------------------
    def desktop_shortcut_path(self) -> str:
        """مسار اختصار سطح المكتب المتوقع (يُستخدم لمعرفة إن كان موجودًا)."""
        from src.utils.winapi import desktop_dir

        return os.path.join(desktop_dir(), f"{APP_NAME}.lnk")

    def start_menu_shortcut_path(self) -> str:
        from src.utils.winapi import start_menu_programs_dir

        return os.path.join(start_menu_programs_dir(), APP_NAME, f"{APP_NAME}.lnk")

    def has_desktop_shortcut(self) -> bool:
        return os.path.exists(self.desktop_shortcut_path())

    def has_start_menu_shortcut(self) -> bool:
        return os.path.exists(self.start_menu_shortcut_path())

    def create_desktop_shortcut(self) -> ActionResult:
        if not IS_WINDOWS:
            return ActionResult(False, "الاختصارات متاحة على ويندوز فقط.")
        path = create_app_shortcut("desktop", icon_path=app_icon_path())
        if path:
            self._remember("desktop_shortcut", True)
            return ActionResult(True, "تم إنشاء اختصار على سطح المكتب.", data={"path": path})
        # بديل: نسخة في مجلد بيانات البرنامج + إرشاد المستخدم
        fallback_dir = shortcuts_dir()
        os.makedirs(fallback_dir, exist_ok=True)
        return ActionResult(
            False,
            f"تعذر إنشاء الاختصار على سطح المكتب. جرّب يدويًا: انسخ اختصارًا من {fallback_dir}.",
        )

    def create_start_menu_shortcut(self) -> ActionResult:
        if not IS_WINDOWS:
            return ActionResult(False, "الاختصارات متاحة على ويندوز فقط.")
        path = create_app_shortcut("start_menu", icon_path=app_icon_path())
        if path:
            self._remember("start_menu_shortcut", True)
            return ActionResult(True, "تم إضافة اختصار في قائمة ابدأ.", data={"path": path})
        return ActionResult(False, "تعذر إنشاء اختصار قائمة ابدأ.")

    def remove_shortcuts(self) -> ActionResult:
        removed = 0
        for path in (self.desktop_shortcut_path(), self.start_menu_shortcut_path()):
            if os.path.exists(path) and remove_shortcut(path):
                removed += 1
        self._remember("desktop_shortcut", False)
        self._remember("start_menu_shortcut", False)
        return ActionResult(True, f"تم حذف {removed} اختصار.")

    # ------------------------------------------------------------------
    # التشغيل مع ويندوز
    # ------------------------------------------------------------------
    def set_run_at_startup(self, enabled: bool, minimized: bool = False) -> ActionResult:
        if not IS_WINDOWS:
            return ActionResult(False, "التشغيل التلقائي متاح على ويندوز فقط.")
        arguments = "--minimized" if minimized else ""
        ok = set_run_at_startup(APP_NAME, enabled, arguments=arguments)
        if ok:
            self._remember("run_with_windows", enabled)
            self._remember("start_minimized", bool(minimized))
            text = "تم تفعيل التشغيل التلقائي مع ويندوز" + (" (مصغّرًا في شريط المهام)" if minimized else "") + "."
            return ActionResult(True, text)
        return ActionResult(False, "تعذر تغيير إعداد التشغيل التلقائي.")

    def is_run_at_startup(self) -> bool:
        return is_run_at_startup(APP_NAME)

    # ------------------------------------------------------------------
    # استثناءات Windows Defender
    # ------------------------------------------------------------------
    def defender_exclusion_targets(self) -> list[str]:
        """المسارات التي يُنصح باستثنائها (مجلد البرنامج + ملف التشغيل)."""
        from src.utils.paths import app_data_dir

        targets = {executable_dir(), app_data_dir()}
        if IS_WINDOWS:
            import sys

            targets.add(os.path.dirname(os.path.abspath(sys.executable)))
        return sorted(t for t in targets if t and os.path.isabs(t))

    def add_defender_exclusions(self) -> ActionResult:
        """
        إضافة البرنامج لمستثنيات Microsoft Defender لتقليل الإنذارات الكاذبة
        (يحتاج صلاحيات مدير). لا يلمس أي إعداد حماية آخر.
        """
        if not IS_WINDOWS:
            return ActionResult(False, "استثناءات Defender متاحة على ويندوز فقط.")
        if not is_admin():
            return ActionResult(False, "إضافة استثناءات Defender تتطلب صلاحيات مدير.")

        paths = self.defender_exclusion_targets()
        quoted = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
        script = (
            "$ErrorActionPreference='SilentlyContinue';"
            f"Add-MpPreference -ExclusionPath @({quoted});"
            "$ErrorActionPreference='Continue';"
            "(Get-MpPreference).ExclusionPath -join ';'"
        )
        result = run_powershell(script, timeout=120)
        if result.ok:
            return ActionResult(
                True,
                "تمت إضافة استثناءات Defender لمجلدات البرنامج.",
                details=result.output,
                data={"paths": paths},
            )
        return ActionResult(False, "تعذرت إضافة استثناءات Defender.", details=result.output)

    def remove_defender_exclusions(self) -> ActionResult:
        if not IS_WINDOWS:
            return ActionResult(False, "استثناءات Defender متاحة على ويندوز فقط.")
        if not is_admin():
            return ActionResult(False, "تعديل استثناءات Defender يتطلب صلاحيات مدير.")
        quoted = ",".join(
            "'" + p.replace("'", "''") + "'" for p in self.defender_exclusion_targets()
        )
        script = f"$ErrorActionPreference='SilentlyContinue'; Remove-MpPreference -ExclusionPath @({quoted}); 'done'"
        result = run_powershell(script, timeout=120)
        if result.ok:
            return ActionResult(True, "تمت إزالة استثناءات Defender الخاصة بالبرنامج.")
        return ActionResult(False, "تعذرت إزالة استثناءات Defender.", details=result.output)

    # ------------------------------------------------------------------
    def installation_summary(self) -> dict:
        """ملخص حالة التثبيت — يُعرض في الإعدادات وعند الإنهاء."""
        return {
            "desktop_shortcut": self.has_desktop_shortcut(),
            "start_menu_shortcut": self.has_start_menu_shortcut(),
            "run_with_windows": self.is_run_at_startup(),
            "install_dir": executable_dir(),
        }

    # ------------------------------------------------------------------
    def _remember(self, key: str, value) -> None:
        if self.settings is not None:
            section = dict(self.settings.get("shortcuts") or {})
            section[key] = value
            self.settings.set("shortcuts", section)
        if self.notifier is not None:
            self.notifier.info("إعداد", f"{key} = {value}", source="installer")


__all__ = ["SystemInstaller", "app_icon_path"]
