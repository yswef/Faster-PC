"""اختبارات مدير الإعدادات: الدمج، التلف، الترقية، والتحقق."""

import json

from src.config.settings import SettingsManager, deep_merge


def test_defaults_created_on_first_run(tmp_path):
    path = tmp_path / "config.json"
    manager = SettingsManager(str(path))
    assert path.exists()
    assert manager.get("setup_completed") is False
    assert manager.get("schema_version") == 2
    assert "Microsoft.Photos.exe" in manager.get("process_exclusions")


def test_deep_merge_preserves_untouched_keys():
    base = {"monitoring": {"enabled": True, "interval_sec": 2}, "other": 1}
    merged = deep_merge(base, {"monitoring": {"interval_sec": 5}})
    assert merged["monitoring"]["interval_sec"] == 5
    assert merged["monitoring"]["enabled"] is True
    assert merged["other"] == 1


def test_save_merges_and_creates_backup(tmp_path):
    path = tmp_path / "config.json"
    manager = SettingsManager(str(path))
    manager.save({"test_mode": True})
    manager.save({"appearance": {"language": "en"}})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["test_mode"] is True
    assert data["appearance"]["language"] == "en"
    assert (tmp_path / "config.json.bak").exists()


def test_corrupt_config_is_quarantined(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ this is not json", encoding="utf-8")
    manager = SettingsManager(str(path))
    assert manager.get("schema_version") == 2
    assert (tmp_path / "config.json.corrupt.bak").exists()
    # الملف أُعيد بناؤه بصيغة سليمة
    json.loads(path.read_text(encoding="utf-8"))


def test_validate_clamps_out_of_range_values(tmp_path):
    manager = SettingsManager(str(tmp_path / "config.json"))
    manager.save({
        "monitoring": {
            "interval_sec": 999,
            "history_seconds": 5,
            "top_processes": 0,
            "thresholds": {"cpu_percent": 500, "sustained_seconds": 1},
        }
    })
    monitoring = manager.get("monitoring")
    assert monitoring["interval_sec"] == 60
    assert monitoring["history_seconds"] == 60
    assert monitoring["top_processes"] == 3
    assert monitoring["thresholds"]["cpu_percent"] == 100
    assert monitoring["thresholds"]["sustained_seconds"] == 3


def test_migration_protects_photos_app(tmp_path):
    """النسخة القديمة كانت تُدرج تطبيق الصور في قائمة الإنهاء الإجباري — يُنقل للحماية."""
    path = tmp_path / "config.json"
    legacy = {
        "force_kill_list": ["pet.exe", "Microsoft.Photos.exe"],
        "process_exclusions": ["explorer.exe"],
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    manager = SettingsManager(str(path))
    assert "Microsoft.Photos.exe" not in manager.get("force_kill_list")
    assert "Microsoft.Photos.exe" in manager.get("process_exclusions")
    assert manager.get("schema_version") == 2


def test_exclusion_helpers(tmp_path):
    manager = SettingsManager(str(tmp_path / "config.json"))
    assert manager.add_process_exclusion("myapp.exe")
    assert "myapp.exe" in manager.get("process_exclusions")
    # لا تكرار (حتى باختلاف حالة الأحرف)
    manager.add_process_exclusion("MYAPP.EXE")
    assert sum(1 for x in manager.get("process_exclusions") if x.lower() == "myapp.exe") == 1
    assert manager.remove_process_exclusion("myapp.exe")
    assert "myapp.exe" not in manager.get("process_exclusions")

    assert manager.add_protected_app("Microsoft.Photos.exe")
    assert "Microsoft.Photos.exe" in manager.get("protected_apps")
    assert "Microsoft.Photos.exe" in manager.get("process_exclusions")
    manager.remove_protected_app("Microsoft.Photos.exe")
    assert "Microsoft.Photos.exe" not in manager.get("protected_apps")


def test_missing_keys_get_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"test_mode": True}), encoding="utf-8")
    manager = SettingsManager(str(path))
    assert manager.get("test_mode") is True
    assert isinstance(manager.get("monitoring"), dict)
    assert manager.get("notifications")["enabled"] is True
