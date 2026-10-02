"""اختبارات مُحسِّن العمليات/الخدمات/بدء التشغيل على ريجستري وهمي."""

import pytest

import src.core.optimizer as optimizer_module
from src.core.journal import ChangeJournal
from src.core.optimizer import _DISABLED_PREFIX, SystemOptimizer

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


@pytest.fixture()
def journal(tmp_path):
    return ChangeJournal(str(tmp_path / "changes.json"))


@pytest.fixture()
def optimizer(settings, journal, fake_registry, monkeypatch):
    monkeypatch.setattr(optimizer_module, "winreg", fake_registry)
    monkeypatch.setattr(optimizer_module, "registry_available", lambda: True)
    fake_registry.seed("HKCU", RUN_KEY, "OneDrive", r"C:\Users\me\OneDrive.exe /background")
    fake_registry.seed("HKLM", RUN_KEY, "SecurityHealth", r"C:\Windows\System32\SecurityHealthSystray.exe")
    return SystemOptimizer(settings, journal=journal)


def test_list_startup_items(optimizer, fake_registry):
    items = optimizer.list_startup_items()
    names = {item["name"] for item in items}
    assert {"OneDrive", "SecurityHealth"} <= names
    assert all(item["disabled"] is False for item in items)


def test_disable_and_reenable_startup_item(optimizer, fake_registry):
    result = optimizer.set_startup_item_enabled("OneDrive", "HKCU", enabled=False)
    assert result.success
    values = fake_registry.dump("HKCU", RUN_KEY)
    assert _DISABLED_PREFIX + "OneDrive" in values
    assert "OneDrive" not in values

    items = optimizer.list_startup_items()
    onedrive = next(item for item in items if item["original_name"] == "OneDrive")
    assert onedrive["disabled"] is True

    result = optimizer.set_startup_item_enabled(
        _DISABLED_PREFIX + "OneDrive", "HKCU", enabled=True
    )
    assert result.success
    values = fake_registry.dump("HKCU", RUN_KEY)
    assert "OneDrive" in values
    assert _DISABLED_PREFIX + "OneDrive" not in values


def test_undo_restores_startup_item(optimizer, journal, fake_registry):
    optimizer.set_startup_item_enabled("OneDrive", "HKCU", enabled=False)
    entry = journal.latest(1)[0]
    assert entry["kind"] == "startup_item"
    assert journal.can_undo(entry)
    ok, message = journal.undo(entry["id"])
    assert ok, message
    values = fake_registry.dump("HKCU", RUN_KEY)
    assert "OneDrive" in values


def test_protected_service_refused(optimizer):
    result = optimizer.set_service_state("RpcSs", enabled=False)
    assert result.success is False
    assert "محمية" in result.message

    result = optimizer.set_service_state("WinDefend", enabled=False)
    assert result.success is False


def test_service_requires_admin_on_windows(optimizer, monkeypatch):
    monkeypatch.setattr(optimizer_module, "IS_WINDOWS", True)
    monkeypatch.setattr(optimizer_module, "is_admin", lambda: False)
    result = optimizer.set_service_state("DiagTrack", enabled=False)
    assert result.success is False
    assert "مدير" in result.message


def test_service_test_mode_preview(optimizer, settings):
    settings.set("test_mode", True)
    result = optimizer.set_service_state("DiagTrack", enabled=False)
    assert result.success is True
    assert "وضع المعاينة" in result.message


def test_kill_list_respects_protection(settings, journal, monkeypatch):
    settings.set("force_kill_list", ["csrss.exe", "notepad.exe"])
    optimizer = SystemOptimizer(settings, journal=journal)
    settings.set("test_mode", True)
    result = optimizer.kill_unwanted_processes()
    killed_names = {item["name"].lower() for item in result.data["killed"]}
    assert "csrss.exe" not in killed_names  # عملية حرجة محمية دائمًا


def test_high_resource_processes_have_protection_flag(optimizer):
    processes = optimizer.list_high_resource_processes(top_n=5)
    assert processes
    assert all("protected" in process for process in processes)
