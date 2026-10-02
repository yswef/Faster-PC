"""
اختبارات دخان للواجهة (تعمل بدون شاشة عبر offscreen) — تضمن أن كل النوافذ
تُبنى بدون أخطاء وأن الربط بين الخدمات والواجهة سليم.
"""

import pytest

from src.core.app_context import AppContext


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """سياق تطبيق معزول بملفات مؤقتة (لا يلمس إعدادات المستخدم الحقيقية)."""
    from src.config.settings import SettingsManager
    from src.core.journal import ChangeJournal

    settings = SettingsManager(str(tmp_path / "config.json"))
    context = AppContext(settings)
    monkeypatch.setattr(context, "journal", ChangeJournal(str(tmp_path / "changes.json")))
    return context


def test_main_window_builds_all_tabs(qapp, ctx):
    from src.gui.main_window import MainWindow

    window = MainWindow(ctx, {"username": "tester", "role": "admin"})
    assert window.tabs.count() >= 11
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "لوحة الأداء" in titles
    assert "الحماية والاستثناءات" in titles
    assert "الأعطال والصحة" in titles
    assert "سجل التغييرات" in titles
    assert not window.windowIcon().isNull()
    window.close()


def test_main_window_without_admin_hides_users_tab(qapp, ctx):
    from src.gui.main_window import MainWindow

    window = MainWindow(ctx, {"username": "tester", "role": "user"})
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert "المستخدمون" not in titles
    window.close()


def test_settings_window_builds_and_saves(qapp, ctx, tmp_path):
    from src.gui.settings_window import SettingsWindow

    dialog = SettingsWindow(ctx)
    dialog.cb_test_mode.setChecked(True)
    dialog.spin_interval.setValue(5)
    dialog.save_and_close()
    assert ctx.settings.get("test_mode") is True
    assert ctx.settings.get("monitoring")["interval_sec"] == 5
    dialog.close()


def test_setup_wizard_pages_and_account_creation(qapp, tmp_path):
    from src.config.settings import SettingsManager
    from src.core.exclusions import ProtectionManager
    from src.core.installer import SystemInstaller
    from src.gui.setup_wizard import AccountPage, SetupWizard

    settings = SettingsManager(str(tmp_path / "config.json"))
    installer = SystemInstaller(settings)
    protection = ProtectionManager(settings)
    wizard = SetupWizard(settings, installer, protection)
    assert len(wizard.pageIds()) == 6

    account = wizard.findChild(AccountPage)
    account.username_input.setText("tester")
    account.password_input.setText("strongpass123")
    account.confirm_input.setText("different")
    assert account.validatePage() is False  # عدم تطابق كلمتي المرور

    account.confirm_input.setText("strongpass123")
    assert account.validatePage() is True
    assert settings.get("users")[0]["username"] == "tester"

    # منع تكرار نفس الاسم
    account.username_input.setText("tester")
    assert account.validatePage() is False
    wizard.close()


def test_login_window_validates_credentials(qapp, ctx):
    from src.gui.login_window import LoginWindow

    ctx.auth.create_user("tester", "strongpass123", role="admin")
    window = LoginWindow(ctx.settings)
    window.username_input.setText("tester")
    window.password_input.setText("wrong-password")
    window.handle_submit()
    assert window.authenticated_user is None
    assert "غير صحيحة" in window.error_label.text()

    window.password_input.setText("strongpass123")
    window.handle_submit()
    assert window.authenticated_user["username"] == "tester"
    window.close()


def test_notifications_center_dialog(qapp, ctx):
    from src.gui.dialogs import NotificationsCenterDialog

    ctx.notifications.info("عنوان تجريبي", "رسالة")
    dialog = NotificationsCenterDialog(ctx.notifications)
    assert dialog.list_widget.count() == 1
    dialog._clear()
    assert ctx.notifications.history() == []
    dialog.close()


def test_confirm_dialog_requires_checkbox(qapp):
    from src.gui.dialogs import ConfirmDialog

    dialog = ConfirmDialog(
        "اختبار", "رسالة", bullets=["بند أول", "بند ثاني"],
        require_checkbox=True, confirm_text="تنفيذ",
    )
    assert dialog.confirm_button.isEnabled() is False
    dialog.checkbox.setChecked(True)
    assert dialog.confirm_button.isEnabled() is True
    dialog.close()


def test_about_dialog(qapp):
    from src.gui.dialogs import AboutDialog

    dialog = AboutDialog()
    assert dialog.windowTitle()
    dialog.close()
