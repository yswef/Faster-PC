"""
نوافذ حوارية مشتركة: اختيار برامج للحماية، تأكيد العمليات الخطرة،
مركز التنبيهات، تقرير نصي، وحول البرنامج.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.gui.theme import COLORS, LEVEL_ICONS, LEVEL_NAMES_AR
from src.version import APP_COPYRIGHT, APP_DESCRIPTION, APP_NAME, APP_PUBLISHER, APP_URL, APP_VERSION


class ConfirmDialog(QDialog):
    """
    تأكيد عملية خطرة: نص واضح + قائمة ما سيحدث + مربع "أفهم" إلزامي
    للعمليات الحساسة (خصوصًا إنهاء العمليات الجماعي).
    """

    def __init__(self, title: str, message: str, bullets: list[str] | None = None,
                 require_checkbox: bool = False, checkbox_text: str = "أفهم ما سيحدث وأريد المتابعة",
                 confirm_text: str = "تنفيذ", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        if bullets:
            list_widget = QListWidget()
            list_widget.setSelectionMode(QListWidget.NoSelection)
            for text in bullets:
                item = QListWidgetItem(f"• {text}")
                list_widget.addItem(item)
            list_widget.setMaximumHeight(min(160, 24 * len(bullets) + 16))
            layout.addWidget(list_widget)

        self.checkbox = None
        if require_checkbox:
            self.checkbox = QCheckBox(checkbox_text)
            layout.addWidget(self.checkbox)

        buttons = QDialogButtonBox()
        self.confirm_button = buttons.addButton(confirm_text, QDialogButtonBox.AcceptRole)
        self.confirm_button.setObjectName("dangerButton")
        buttons.addButton("إلغاء", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.checkbox is not None:
            self.confirm_button.setEnabled(False)
            self.checkbox.toggled.connect(self.confirm_button.setEnabled)

    def _on_accept(self) -> None:
        if self.checkbox is not None and not self.checkbox.isChecked():
            return
        self.accept()


class ProtectionPickerDialog(QDialog):
    """اختيار برامج جارية (أو ملف exe) لإضافتها لقائمة الحماية/الاستثناء."""

    def __init__(self, protection, parent=None):
        super().__init__(parent)
        self.protection = protection
        self.selected: list[str] = []
        self.setWindowTitle("إضافة برامج للاستثناء والحماية")
        self.setMinimumSize(560, 520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "اختر البرامج التي لا تريد أن يغلقها البرنامج أبدًا، أو حدّد ملف تنفيذي يدويًا.\n"
            "البرامج المحددة تُضاف لقائمة الاستثناءات وقائمة الحماية معًا."
        ))

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث باسم البرنامج...")
        self.search_input.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_input)
        btn_browse = QPushButton("استعراض ملف exe...")
        btn_browse.clicked.connect(self._browse_exe)
        search_row.addWidget(btn_browse)
        layout.addLayout(search_row)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox()
        add_btn = buttons.addButton("إضافة المحدد للحماية", QDialogButtonBox.AcceptRole)
        add_btn.setObjectName("primaryButton")
        buttons.addButton("إلغاء", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._accept_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate()

    def _populate(self) -> None:
        self.list_widget.clear()
        apps = self.protection.list_running_apps()
        for app in apps:
            label = f"{app['name']}  —  {app['memory_mb']} MB"
            if app["protected"]:
                label += "  ✔ محمي حاليًا"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if not app["protected"] else Qt.Unchecked)
            item.setData(Qt.UserRole, app["name"])
            if app["protected"]:
                item.setForeground(Qt.gray)
            self.list_widget.addItem(item)
        self.hint.setText(f"عدد البرامج الجارية المعروضة: {len(apps)}")

    def _apply_filter(self, text: str) -> None:
        text = (text or "").strip().lower()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _browse_exe(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "اختر ملف البرنامج التنفيذي", os.path.expanduser("~"), "ملفات تنفيذية (*.exe);;كل الملفات (*)"
        )
        if path:
            name = os.path.basename(path)
            item = QListWidgetItem(f"{name}  —  {path}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, name)
            self.list_widget.insertItem(0, item)

    def _accept_selected(self) -> None:
        self.selected = [
            self.list_widget.item(i).data(Qt.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.Checked
        ]
        if not self.selected:
            self.hint.setText("لم تحدد أي برنامج.")
            return
        self.accept()


class NotificationsCenterDialog(QDialog):
    """مركز التنبيهات: كل ما أبلغ عنه البرنامج مؤخرًا."""

    def __init__(self, notification_center, parent=None):
        super().__init__(parent)
        self.center = notification_center
        self.setWindowTitle("مركز التنبيهات")
        self.setMinimumSize(520, 460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        btn_read = QPushButton("تحديد الكل كمقروء")
        btn_read.clicked.connect(self._mark_read)
        row.addWidget(btn_read)
        btn_clear = QPushButton("مسح الكل")
        btn_clear.clicked.connect(self._clear)
        row.addWidget(btn_clear)
        row.addStretch()
        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self.center.notification_added.connect(self._refresh)
        self._refresh()

    def _refresh(self, *_args) -> None:
        self.list_widget.clear()
        for note in reversed(self.center.history()):
            icon = LEVEL_ICONS.get(note.level.value, "ℹ")
            label = f"{icon}  [{note.time_text}] {note.title}"
            item = QListWidgetItem(label)
            if note.message:
                item.setToolTip(note.message)
            item.setForeground(Qt.GlobalColor.white)
            item.setData(Qt.UserRole, note)
            self.list_widget.addItem(item)
            # لون جانبي حسب المستوى
            item.setText(f"{icon}  [{note.time_text}] {LEVEL_NAMES_AR.get(note.level.value, '')}: {note.title}")
            item.setForeground(Qt.GlobalColor.white)
            item.setBackground(Qt.transparent)
            if note.message:
                item.setText(item.text() + f"\n      {note.message}")
        if self.list_widget.count() == 0:
            self.list_widget.addItem("لا توجد تنبيهات بعد — كل شيء هادئ.")

    def _mark_read(self) -> None:
        self.center.mark_all_read()

    def _clear(self) -> None:
        self.center.clear()
        self._refresh()


class TextReportDialog(QDialog):
    """عرض تقرير نصي (صحة النظام/تشخيص) مع إمكانية الحفظ."""

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 520)
        layout = QVBoxLayout(self)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view)

        row = QHBoxLayout()
        btn_save = QPushButton("حفظ التقرير...")
        btn_save.clicked.connect(lambda: self._save(text))
        row.addWidget(btn_save)
        row.addStretch()
        btn_close = QPushButton("إغلاق")
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        layout.addLayout(row)

    def _save(self, text: str) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, "حفظ التقرير", "fasterpc_report.txt", "ملفات نصية (*.txt)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                pass


class AboutDialog(QDialog):
    """حول البرنامج — معلومات الإصدار والترخيص."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"حول {APP_NAME}")
        self.setMinimumWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>{APP_NAME} <span style='color:{COLORS['success']}'>{APP_VERSION}</span></h2>")
        layout.addWidget(title)
        description = QLabel(APP_DESCRIPTION)
        description.setWordWrap(True)
        layout.addWidget(description)

        info = QLabel(
            f"<p style='color:{COLORS['text_muted']}'>"
            f"المطوّر: {APP_PUBLISHER}<br>{APP_COPYRIGHT}<br>"
            f"<a href='{APP_URL}' style='color:{COLORS['accent']}'>{APP_URL}</a></p>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


__all__ = [
    "ConfirmDialog",
    "ProtectionPickerDialog",
    "NotificationsCenterDialog",
    "TextReportDialog",
    "AboutDialog",
]
