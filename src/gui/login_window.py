from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt

from src.utils.auth import AuthManager, AuthError


class LoginWindow(QDialog):
    """
    نافذة تسجيل الدخول. لو ما فيه أي مستخدم مسجّل بعد (أول تشغيل للبرنامج)،
    تتحول تلقائيًا لنموذج "إنشاء حساب المدير الأول".
    """

    def __init__(self, settings_manager):
        super().__init__()
        self.settings = settings_manager
        self.auth = AuthManager(settings_manager)
        self.authenticated_user = None

        self.first_run = not self.auth.has_any_users()
        self.setWindowTitle("إنشاء حساب المدير" if self.first_run else "تسجيل الدخول")
        self.setMinimumWidth(340)
        self.setModal(True)

        layout = QVBoxLayout()
        form = QFormLayout()

        if self.first_run:
            layout.addWidget(QLabel("مرحبًا بك لأول مرة! أنشئ حساب المدير الرئيسي:"))

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form.addRow("اسم المستخدم:", self.username_input)
        form.addRow("كلمة المرور:", self.password_input)

        if self.first_run:
            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.Password)
            form.addRow("تأكيد كلمة المرور:", self.confirm_input)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        btn_text = "إنشاء الحساب والدخول" if self.first_run else "دخول"
        self.submit_btn = QPushButton(btn_text)
        self.submit_btn.setObjectName("runButton")
        self.submit_btn.clicked.connect(self.handle_submit)
        layout.addWidget(self.submit_btn)

        self.password_input.returnPressed.connect(self.handle_submit)

        self.setLayout(layout)

    def handle_submit(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if self.first_run:
            confirm = self.confirm_input.text()
            if password != confirm:
                self.error_label.setText("كلمتا المرور غير متطابقتين.")
                return
            try:
                self.auth.create_user(username, password, role="admin")
            except AuthError as e:
                self.error_label.setText(str(e))
                return
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"تعذر إنشاء الحساب: {e}")
                return

            self.authenticated_user = self.auth.authenticate(username, password)
            self.accept()
            return

        try:
            user = self.auth.authenticate(username, password)
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"تعذر التحقق من الحساب: {e}")
            return

        if user is None:
            self.error_label.setText("اسم المستخدم أو كلمة المرور غير صحيحة.")
            return

        self.authenticated_user = user
        self.accept()
