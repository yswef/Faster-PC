"""اختبارات التنظيف — التركيز على حواجز الأمان (منع الهروب من المجلد المستهدف)."""

import os
import sys

import pytest

from src.core.cleaner import SystemCleaner


@pytest.fixture()
def cleaner(settings):
    return SystemCleaner(settings)


def test_symlink_escape_is_refused(cleaner, tmp_path):
    """رابط رمزي داخل Temp يشاور على ملف خارجها — لا يجوز حذفه أو اتباعه."""
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks not supported")
    base = tmp_path / "temp"
    base.mkdir()
    outside = tmp_path / "important.txt"
    outside.write_text("important data", encoding="utf-8")
    link = base / "sneaky"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlink in this environment")

    report = {"removed": 0, "skipped": 0, "freed": 0, "locked": 0}
    cleaner._delete_item(str(link), str(base), test_mode=False, report=report)
    # الرابط نُظّف (إن كان داخليًا) لكن الملف الأصلي لم يُمس
    assert outside.exists()
    assert outside.read_text(encoding="utf-8") == "important data"


def test_path_outside_base_refused(cleaner, tmp_path):
    base = tmp_path / "temp"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep me", encoding="utf-8")
    report = {"removed": 0, "skipped": 0, "freed": 0, "locked": 0}
    cleaner._delete_item(str(outside), str(base), test_mode=False, report=report)
    assert outside.exists()
    assert report["skipped"] == 1


def test_clean_directory_removes_files(cleaner, tmp_path):
    target = tmp_path / "cache"
    target.mkdir()
    for index in range(5):
        (target / f"file{index}.tmp").write_text("x" * 100, encoding="utf-8")
    report = {"removed": 0, "skipped": 0, "freed": 0, "locked": 0}
    cleaner._clean_directory(str(target), test_mode=False, report=report, label="اختبار")
    assert report["removed"] == 5
    assert report["freed"] == 500
    assert os.listdir(target) == []


def test_test_mode_does_not_delete(cleaner, tmp_path):
    target = tmp_path / "cache"
    target.mkdir()
    (target / "keep.tmp").write_text("data", encoding="utf-8")
    report = {"removed": 0, "skipped": 0, "freed": 0, "locked": 0}
    cleaner._clean_directory(str(target), test_mode=True, report=report, label="اختبار")
    assert (target / "keep.tmp").exists()
    assert report["removed"] == 1


def test_summarize_reports_freed_size(cleaner):
    report = {"removed": 3, "skipped": 1, "freed": 2 * 1024 * 1024, "locked": 1}
    result = cleaner._summarize(report, "تنظيف تجريبي")
    assert result.success is True
    assert "2.0 MB" in result.message


def test_recycle_bin_in_test_mode(cleaner, settings):
    settings.set("test_mode", True)
    result = cleaner.clean_recycle_bin()
    assert result.success is True
    assert "وضع المعاينة" in result.message


def test_temp_directories_include_windows_temp(cleaner):
    dirs = cleaner.temp_directories(include_user_temp=True)
    if sys.platform == "win32":
        assert any("Temp" in path for path, _label in dirs)
    else:
        assert dirs  # على الأنظمة الأخرى يوجد مجلد مؤقت واحد على الأقل
