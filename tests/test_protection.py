"""اختبارات مدير الحماية — الحد الحاسم بين البرنامج وإغلاق عمليات النظام."""

import os

import psutil

from src.core.exclusions import HARD_PROTECTED_PROCESSES, ProtectionManager


def _manager(settings):
    return ProtectionManager(settings, own_pid=os.getpid())


def test_hard_protected_processes_always_blocked(settings):
    protection = _manager(settings)
    for name in ("csrss.exe", "lsass.exe", "wininit.exe", "System", "smss.exe"):
        allowed, reason = protection.check_process(name=name, pid=4)
        assert allowed is False
        assert "حرجة" in reason
    assert "lsass.exe" in HARD_PROTECTED_PROCESSES


def test_user_exclusions_block_termination(settings):
    settings.add_process_exclusion("mychrome.exe")
    protection = _manager(settings)
    allowed, reason = protection.check_process(name="mychrome.exe", pid=1234)
    assert allowed is False
    assert "مستثناة" in reason


def test_own_process_is_protected(settings):
    protection = _manager(settings)
    allowed, reason = protection.check_process(name="python", pid=os.getpid())
    assert allowed is False


def test_own_children_are_protected(settings):
    protection = _manager(settings)
    child = psutil.Process(os.getpid())
    allowed, reason = protection.check_process(child)
    assert allowed is False


def test_ordinary_process_is_allowed(settings):
    protection = _manager(settings)
    allowed, reason = protection.check_process(name="notepad.exe", pid=4242)
    assert allowed is True
    assert reason == ""


def test_photos_app_protected_by_default(settings):
    """تطبيق الصور محمي افتراضيًا — لا يُغلق من البرنامج أبدًا."""
    protection = _manager(settings)
    allowed, _reason = protection.check_process(name="Microsoft.Photos.exe", pid=999)
    assert allowed is False


def test_protected_apps_are_added_to_exclusions(settings):
    protection = _manager(settings)
    assert protection.add_app_to_protection("game.exe")
    assert "game.exe" in protection.user_protected_apps
    assert "game.exe" in protection.exclusions
    allowed, reason = protection.check_process(name="game.exe", pid=555)
    assert allowed is False
    assert "محمية" in reason
    protection.remove_app_from_protection("game.exe")
    assert "game.exe" not in protection.user_protected_apps


def test_hard_protected_services(settings):
    protection = _manager(settings)
    blocked, reason = protection.is_service_protected("RpcSs")
    assert blocked is True
    blocked, reason = protection.is_service_protected("WinDefend")
    assert blocked is True
    allowed, _ = protection.is_service_protected("SysMain")
    assert allowed is False


def test_summary_counts(settings):
    protection = _manager(settings)
    summary = protection.summary()
    assert summary["hard_protected_count"] >= 15
    assert summary["exclusions_count"] >= 20
    assert summary["hard_protected_services_count"] >= 4


def test_list_running_apps_returns_current_process(settings):
    protection = _manager(settings)
    apps = protection.list_running_apps(include_system=True)
    assert any(app["name"].lower().startswith("python") for app in apps)
