"""
عناصر الواجهة المشتركة: بطاقات إحصائية، رسوم بيانية مصغّرة (Sparklines)،
تنبيهات منبثقة (Toast)، وعدّاد شارة.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.theme import COLORS, LEVEL_COLORS, LEVEL_ICONS, gauge_color


class Card(QFrame):
    """إطار موحّد لعناصر الواجهة (عنوان اختياري + جسم)."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("cardTitle")
            self._layout.addWidget(label)

    def add(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def body(self) -> QVBoxLayout:
        return self._layout


class Sparkline(QWidget):
    """رسم بياني مصغّر لقيمة متغيرة زمنيًا (بدون مكتبات خارجية)."""

    def __init__(self, color: str = COLORS["accent"], max_value: float = 100.0, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self._color = color
        self._max = max_value
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_values(self, values) -> None:
        self._values = [float(v) for v in (values or [])][-240:]
        self.update()

    def set_max(self, value: float) -> None:
        """تحديد أعلى قيمة للمقياس (يُستخدم للمؤشرات غير المئوية مثل سرعة الشبكة)."""
        self._max = max(1.0, float(value or 1.0))

    def set_color(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["panel_alt"]))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(rect, 6, 6)

        if len(self._values) < 2:
            return

        width = max(1, rect.width() - 4)
        height = max(1, rect.height() - 6)
        step = width / (len(self._values) - 1)
        top = rect.top() + 3

        points = []
        for index, value in enumerate(self._values):
            ratio = min(1.0, max(0.0, value / self._max if self._max else 0.0))
            x = rect.left() + 2 + index * step
            y = top + height * (1.0 - ratio)
            points.append(QPoint(int(x), int(y)))

        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)

        area = QPainterPath(path)
        area.lineTo(points[-1].x(), rect.bottom() - 3)
        area.lineTo(points[0].x(), rect.bottom() - 3)
        area.closeSubpath()

        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        fill = QColor(self._color)
        fill.setAlpha(70)
        gradient.setColorAt(0.0, fill)
        fill_bottom = QColor(self._color)
        fill_bottom.setAlpha(5)
        gradient.setColorAt(1.0, fill_bottom)

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(area)

        painter.setPen(QPen(QColor(self._color), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)


class StatCard(Card):
    """بطاقة إحصائية: عنوان + قيمة كبيرة + وصف + رسم بياني."""

    def __init__(self, title: str, unit: str = "%", color: str = COLORS["accent"], parent=None):
        super().__init__(parent)
        self._unit = unit
        self._color = color

        row = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statTitle")
        row.addWidget(self.title_label)
        row.addStretch()
        row.addWidget(QLabel(""))

        self.value_label = QLabel("—")
        self.value_label.setObjectName("statValue")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.value_label.setFont(font)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("statSubtitle")

        self.sparkline = Sparkline(color=color, parent=self)

        header = QHBoxLayout()
        header.addWidget(self.value_label)
        header.addStretch()
        self.badge = QLabel("")
        self.badge.setObjectName("statBadge")
        header.addWidget(self.badge)
        header.setAlignment(self.badge, Qt.AlignTop)

        self.setMinimumWidth(180)
        self.add(self.title_label)
        self.add_layout(header)
        self.add(self.subtitle_label)
        self.add(self.sparkline)

    def update_value(self, value: float | None, text: str = "", subtitle: str = "",
                     history=None, color: str | None = None) -> None:
        if text:
            self.value_label.setText(text)
        elif value is not None:
            self.value_label.setText(f"{value:.0f}{self._unit}")
        color = color or (gauge_color(value) if value is not None else self._color)
        self.value_label.setStyleSheet(f"color: {color};")
        self.sparkline.set_color(color)
        if history is not None:
            self.sparkline.set_values(history)
        self.subtitle_label.setText(subtitle)


class Toast(QFrame):
    """رسالة منبثقة صغيرة تظهر في زاوية النافذة وتختفي تلقائيًا."""

    clicked = Signal()

    def __init__(self, title: str, message: str, level: str, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        color = LEVEL_COLORS.get(level, COLORS["accent"])
        self.setStyleSheet(
            f"QFrame#toast {{ background-color: {COLORS['panel_alt']};"
            f" border: 1px solid {color}; border-radius: 8px; }}"
            f"QLabel {{ color: {COLORS['text']}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        head = QLabel(f"{LEVEL_ICONS.get(level, 'ℹ')}  {title}")
        head.setStyleSheet(f"color: {color}; font-weight: 700;")
        layout.addWidget(head)

        if message:
            body = QLabel(message)
            body.setWordWrap(True)
            body.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
            layout.addWidget(body)

        self.setMaximumWidth(360)
        self.setMinimumWidth(260)
        self.adjustSize()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit()
        super().mousePressEvent(event)


class ToastManager:
    """يدير ظهور عدة رسائل منبثقة فوق النافذة (بدون تراكب)."""

    def __init__(self, parent: QWidget, limit: int = 3, timeout_ms: int = 7000):
        self.parent = parent
        self.limit = limit
        self.timeout_ms = timeout_ms
        self._toasts: list[Toast] = []

    def show_message(self, title: str, message: str = "", level: str = "info") -> None:
        if not self.parent.isVisible():
            return
        toast = Toast(title, message, level, self.parent)
        toast.clicked.connect(self._dismiss_all)
        toast.show()
        toast.adjustSize()
        self._toasts.append(toast)
        while len(self._toasts) > self.limit:
            self._remove(self._toasts[0])
        self._reposition()
        QTimer.singleShot(self.timeout_ms, lambda: self._remove(toast))

    def _remove(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        toast.deleteLater()
        self._reposition()

    def _dismiss_all(self) -> None:
        for toast in list(self._toasts):
            self._remove(toast)

    def _reposition(self) -> None:
        margin = 16
        offset = 0
        for toast in reversed(self._toasts):
            toast.adjustSize()
            x = self.parent.width() - toast.width() - margin
            y = margin + offset
            toast.move(max(0, x), max(0, y))
            offset += toast.height() + 8
            toast.raise_()


class SectionHeader(QLabel):
    """عنوان قسم داخل التبويبات."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("sectionHeader")


def make_grid(*widgets_with_positions) -> QGridLayout:
    """GridLayout مختصر: [(widget, row, col), ...]"""
    grid = QGridLayout()
    for widget, row, col in widgets_with_positions:
        grid.addWidget(widget, row, col)
    return grid


__all__ = ["Card", "Sparkline", "StatCard", "Toast", "ToastManager", "SectionHeader", "make_grid"]
