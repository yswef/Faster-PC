"""
الألوان والثوابت البصرية — مصدر واحد لكل عناصر الواجهة.

يحافظ على نفس هوية المشروع (خلفية داكنة + أخضر أساسي) مع إضافة ألوان حالة
واضحة (نجاح/تحذير/خطر) تُستخدم في البطاقات والتنبيهات والرسوم البيانية.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

from src.utils.paths import resource_path

COLORS = {
    "bg": "#16171d",
    "panel": "#1e1f26",
    "panel_alt": "#24262f",
    "border": "#2e303c",
    "text": "#e6e6e6",
    "text_muted": "#9a9dab",
    "accent": "#4a90e2",
    "success": "#3fbf7f",
    "warning": "#f0ad4e",
    "danger": "#e74c3c",
    "purple": "#8b5cf6",
}

LEVEL_COLORS = {
    "info": COLORS["accent"],
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "error": COLORS["danger"],
}

LEVEL_ICONS = {
    "info": "ℹ",
    "success": "✔",
    "warning": "⚠",
    "error": "⛔",
}

LEVEL_NAMES_AR = {
    "info": "معلومة",
    "success": "نجاح",
    "warning": "تحذير",
    "error": "خطأ",
}


def gauge_color(percent: float) -> str:
    """لون حسب نسبة الاستهلاك (أخضر < 60، برتقالي < 85، أحمر بعدها)."""
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return COLORS["success"]
    if value >= 85:
        return COLORS["danger"]
    if value >= 60:
        return COLORS["warning"]
    return COLORS["success"]


def dark_palette() -> QPalette:
    """
    لوحة ألوان داكنة لتطبيق Qt — تضمن أن أي عنصر لا يغطيه ملف الأنماط
    (مثل صفحات المعالج QWizardPage وحوارات النظام) يظهر داكنًا ومقروءًا.
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Base, QColor(COLORS["panel"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["panel_alt"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.Button, QColor(COLORS["panel_alt"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.BrightText, QColor(COLORS["danger"]))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["panel_alt"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.PlaceholderText, QColor(COLORS["text_muted"]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#6a6d7a"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#6a6d7a"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#6a6d7a"))
    return palette


def stylesheet() -> str:
    """قراءة ملف الأنماط مع بديل مدمج لو الملف مفقود."""
    path = resource_path("src/gui/styles.qss")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return _FALLBACK_QSS


_FALLBACK_QSS = f"""
QMainWindow, QDialog {{ background-color: {COLORS['panel']}; }}
QLabel {{ color: {COLORS['text']}; }}
QPushButton {{
    background-color: {COLORS['panel_alt']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px 12px;
}}
QPushButton:hover {{ background-color: #333648; }}
QPushButton#primaryButton {{ background-color: {COLORS['success']}; border: none; font-weight: 700; }}
QPushButton#dangerButton {{ background-color: {COLORS['danger']}; border: none; font-weight: 700; }}
"""


__all__ = [
    "COLORS",
    "LEVEL_COLORS",
    "LEVEL_ICONS",
    "LEVEL_NAMES_AR",
    "gauge_color",
    "dark_palette",
    "stylesheet",
]
