"""اختبارات سجل التغييرات ومركز التنبيهات."""

import src.core.tweaks as tweaks_module
from src.core.journal import ChangeJournal
from src.core.notifications import Level, NotificationCenter
from src.core.tweaks import PerformanceTweaks


def test_journal_records_and_persists(tmp_path):
    path = tmp_path / "changes.json"
    journal = ChangeJournal(str(path))
    journal.record("test", "تغيير تجريبي", {"a": 1})
    assert path.exists()

    reloaded = ChangeJournal(str(path))
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0]["description"] == "تغيير تجريبي"


def test_journal_undo_with_handler(tmp_path):
    journal = ChangeJournal(str(tmp_path / "changes.json"))
    state = {"value": "new"}

    def handler(entry):
        state["value"] = entry["data"]["previous"]
        return True, "تم التراجع"

    journal.register_undo_handler("demo", handler)
    entry = journal.record("demo", "تغيير", {"previous": "old"})
    assert journal.can_undo(entry)

    ok, message = journal.undo(entry["id"])
    assert ok and message == "تم التراجع"
    assert state["value"] == "old"
    assert journal.can_undo(entry) is False  # لا يُتراجع مرتين


def test_journal_without_handler(tmp_path):
    journal = ChangeJournal(str(tmp_path / "changes.json"))
    entry = journal.record("no_handler", "تغيير")
    ok, message = journal.undo(entry["id"])
    assert ok is False
    assert "لا يدعم" in message


def test_journal_corrupt_file_is_tolerated(tmp_path):
    path = tmp_path / "changes.json"
    path.write_text("{ bad json", encoding="utf-8")
    journal = ChangeJournal(str(path))
    assert journal.entries == []


def test_notifications_unread_counter(settings):
    center = NotificationCenter(settings)
    events = []
    center.notification_added.connect(events.append)
    center.info("عنوان", "رسالة")
    center.warning("تحذير")
    assert center.unread_count() == 2
    assert len(events) == 2
    center.mark_all_read()
    assert center.unread_count() == 0


def test_notifications_disabled_but_errors_pass(settings):
    settings.set("notifications", {"enabled": False})
    center = NotificationCenter(settings)
    center.info("لن تظهر")
    center.error("خطأ حرج")
    history = center.history()
    assert len(history) == 1
    assert history[0].level == Level.ERROR


def test_notification_to_dict(settings):
    center = NotificationCenter(settings)
    note = center.success("تم")
    data = note.to_dict()
    assert data["level"] == "success"
    assert "timestamp" in data


def test_registry_tweaks_undo(settings, tmp_path, monkeypatch, fake_registry):
    """تحسين ريجستري ثم تراجع عنه يعيد القيمة السابقة."""
    journal = ChangeJournal(str(tmp_path / "changes.json"))
    monkeypatch.setattr(tweaks_module, "winreg", fake_registry)
    monkeypatch.setattr(tweaks_module, "registry_available", lambda: True)
    monkeypatch.setattr(tweaks_module, "read_value", fake_registry.QueryValueEx)
    monkeypatch.setattr(tweaks_module, "is_admin", lambda: True)

    def _read(root, path, name, default=None):
        try:
            return fake_registry.QueryValueEx(fake_registry.OpenKey(root, path), name)[0]
        except FileNotFoundError:
            return default

    monkeypatch.setattr(tweaks_module, "read_value", _read)

    def _write(root, path, name, value, value_type=None):
        key = fake_registry.CreateKeyEx(root, path)
        fake_registry.SetValueEx(
            key, name, 0, value_type or fake_registry.REG_DWORD, value
        )
        return True

    monkeypatch.setattr(tweaks_module, "write_value", _write)

    def _delete(root, path, name):
        try:
            fake_registry.DeleteValue(fake_registry.OpenKey(root, path), name)
        except FileNotFoundError:
            pass
        return True

    monkeypatch.setattr(tweaks_module, "delete_value", _delete)

    tweaks = PerformanceTweaks(settings, journal=journal)
    settings.set("test_mode", False)
    result = tweaks.disable_background_apps()
    assert result.success, result.message
    path = r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
    assert fake_registry.dump("HKCU", path)["GlobalUserDisabled"][0] == 1

    entry = journal.latest(1)[0]
    ok, message = journal.undo(entry["id"])
    assert ok, message
    values = fake_registry.dump("HKCU", path)
    assert "GlobalUserDisabled" not in values  # القيمة ما كانت موجودة قبلنا


def test_tweak_test_mode_does_not_write(settings, tmp_path, monkeypatch, fake_registry):
    journal = ChangeJournal(str(tmp_path / "changes.json"))
    monkeypatch.setattr(tweaks_module, "winreg", fake_registry)
    monkeypatch.setattr(tweaks_module, "registry_available", lambda: True)
    monkeypatch.setattr(tweaks_module, "read_value", lambda *a, **k: None)
    written = []
    monkeypatch.setattr(tweaks_module, "write_value", lambda *a, **k: written.append(a) or True)

    tweaks = PerformanceTweaks(settings, journal=journal)
    settings.set("test_mode", True)
    result = tweaks.set_visual_effects_best_performance()
    assert result.success
    assert "وضع المعاينة" in result.message
    assert written == []
    assert journal.latest(1) == []


def test_memory_integrity_requires_confirmation(settings):
    tweaks = PerformanceTweaks(settings)
    result = tweaks.toggle_memory_integrity(False, confirm=False)
    assert result.success is False
    assert "تأكيد" in result.message
