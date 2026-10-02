"""
أداة مطوّر: تشغيل الواجهة بدون شاشة (offscreen) وحفظ صور لكل تبويب.

الاستخدام:
    QT_QPA_PLATFORM=offscreen python tools/ui_preview.py [مجلد الصور]

الفائدة: مراجعة شكل الواجهة بسرعة بعد أي تغيير، والتأكد أن كل التبويبات
تُبنى بدون أخطاء.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.app_context import AppContext  # noqa: E402
from src.gui.login_window import LoginWindow  # noqa: E402
from src.gui.main_window import MainWindow  # noqa: E402
from src.gui.settings_window import SettingsWindow  # noqa: E402
from src.gui.setup_wizard import SetupWizard  # noqa: E402


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    from src.gui.theme import dark_palette

    app.setPalette(dark_palette())
    ctx = AppContext()
    window = MainWindow(ctx, {"username": "preview", "role": "admin"})
    window.resize(1280, 820)
    window.show()
    app.processEvents()

    names = []
    for index in range(window.tabs.count()):
        window.tabs.setCurrentIndex(index)
        app.processEvents()
        name = window.tabs.tabText(index).replace(" ", "_").replace("/", "-")
        names.append(name)
        window.grab().save(str(out_dir / f"{index:02d}_{name}.png"))

    settings = SettingsWindow(ctx, window)
    settings.show()
    app.processEvents()
    settings.grab().save(str(out_dir / "settings.png"))

    login = LoginWindow(ctx.settings)
    login.show()
    app.processEvents()
    login.grab().save(str(out_dir / "login.png"))

    wizard = SetupWizard(ctx.settings, ctx.installer, ctx.protection, window)
    wizard.show()
    for page_id in range(wizard.pageIds().__len__()):
        wizard.setCurrentId(wizard.pageIds()[page_id])
        app.processEvents()
        wizard.grab().save(str(out_dir / f"setup_{page_id}.png"))
    wizard.close()

    print("Saved previews:", ", ".join(names), "+ settings.png, login.png, setup_*.png")
    print("Output:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
