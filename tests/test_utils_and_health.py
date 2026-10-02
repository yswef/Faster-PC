"""اختبارات الأدوات المساعدة، المراقبة، والصحة."""

import os
import sys

from src.core.health import HealthMonitor
from src.core.monitor import PerformanceMonitor
from src.utils.paths import human_size, resource_path, writable_path
from src.utils.winapi import CommandResult, hidden_process_kwargs, run_silent, windows_drive


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(512) == "512 B"
    assert human_size(2048) == "2.0 KB"
    assert human_size(5 * 1024 ** 2) == "5.0 MB"
    assert human_size(3 * 1024 ** 3) == "3.0 GB"
    assert human_size(None) == "0 B"


def test_resource_path_exists_for_runtime_resources():
    assert os.path.exists(resource_path("src/gui/styles.qss"))
    assert os.path.exists(resource_path("docs/docs.html"))
    assert os.path.exists(resource_path("assets/app_icon.ico"))


def test_writable_path_is_absolute():
    assert os.path.isabs(writable_path("config.json"))


def test_run_silent_captures_output():
    result = run_silent([sys.executable, "-c", "print('hello faster pc')"], timeout=30)
    assert isinstance(result, CommandResult)
    assert result.ok
    assert "hello faster pc" in result.stdout


def test_run_silent_missing_command():
    result = run_silent(["definitely-not-a-real-command-xyz"], timeout=10)
    assert result.ok is False
    assert result.error


def test_run_silent_string_command():
    result = run_silent(f'"{sys.executable}" -c "print(123)"', timeout=30)
    assert "123" in result.stdout


def test_hidden_kwargs_only_on_windows():
    kwargs = hidden_process_kwargs()
    if os.name == "nt":
        assert kwargs
    else:
        assert kwargs == {}


def test_windows_drive_value():
    drive = windows_drive()
    assert drive
    if os.name == "nt":
        assert drive.endswith("\\")


def test_monitor_collect_snapshot(qapp, settings):
    monitor = PerformanceMonitor(settings)
    snapshot = monitor.collect()
    assert 0 <= snapshot["cpu_percent"] <= 100
    assert snapshot["ram_total_mb"] > 0
    assert "history" in snapshot
    assert isinstance(snapshot["top_processes"], list)
    # لقطة ثانية تُحدّث التاريخ
    monitor.collect()
    assert len(monitor.cpu_history) >= 1


def test_monitor_threshold_detection(qapp, settings):
    settings.set("monitoring", {
        "enabled": True,
        "interval_sec": 1,
        "thresholds": {"cpu_percent": 1, "ram_percent": 1, "disk_percent": 1, "sustained_seconds": 0},
        "notify_on_threshold": True,
    })
    monitor = PerformanceMonitor(settings)
    events = []
    monitor.threshold_exceeded.connect(lambda metric, value: events.append(metric))
    for _ in range(4):
        monitor.collect()
    assert events  # مع حد 1% يجب أن يتحقق التنبيه بعد كفاية الوقت


def test_health_summarize_contains_sections():
    report = {
        "windows": {"name": "Windows 11", "version": "23H2", "build": "22631.1"},
        "uptime_hours": 5.0,
        "system_errors_24h": 2,
        "disks": [{"mount": "C:\\", "free_gb": 100.0, "percent": 40.0}],
        "recent_crashes": [{"timestamp": "2026-01-01 10:00:00", "app": "game.exe", "kind": "توقف مفاجئ"}],
        "generated": "2026-01-01T10:00:00",
    }
    text = HealthMonitor.summarize(report)
    assert "Windows 11" in text
    assert "game.exe" in text
    assert "C:\\" in text


def test_health_report_collects_without_event_log(qapp, settings):
    settings.set("health", {"enabled": True, "watch_event_log": False, "low_disk_gb": 1})
    monitor = HealthMonitor(settings)
    report = monitor.collect_report()
    assert "disks" in report
    assert isinstance(report["issues"], list)
    assert report["recent_crashes"] == []
