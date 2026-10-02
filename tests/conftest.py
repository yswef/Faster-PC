"""
تهيئة الاختبارات: تعمل على أي نظام (ويندوز أو لينكس) بدون واجهة ظاهرة.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def qapp():
    """تطبيق Qt واحد لكل الجلسة (بدون نوافذ)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    """مدير إعدادات معزول بملف مؤقت لكل اختبار."""
    from src.config.settings import SettingsManager

    config_file = tmp_path / "config.json"
    manager = SettingsManager(str(config_file))
    monkeypatch.setattr(manager, "config_path", str(config_file))
    return manager


from src.utils.registry import winreg as _winreg  # noqa: E402

HKCU = _winreg.HKEY_CURRENT_USER
HKLM = _winreg.HKEY_LOCAL_MACHINE


class FakeWinReg:
    """
    ريجستري وهمي بالذاكرة لاختبار منطق برامج بدء التشغيل والتحسينات
    بدون أي تعديل حقيقي على النظام. يستخدم نفس ثوابت HKEY التي يستخدمها
    البرنامج حتى تكون الاختبارات واقعية.
    """

    HKEY_CURRENT_USER = HKCU
    HKEY_LOCAL_MACHINE = HKLM

    _ALIASES = {
        "HKCU": HKCU, "HKLM": HKLM,
        HKCU: HKCU, HKLM: HKLM,
    }

    @classmethod
    def _hive(cls, hive):
        return cls._ALIASES.get(hive, hive)

    KEY_READ = 1
    KEY_SET_VALUE = 2
    KEY_ALL_ACCESS = 3

    REG_SZ = 1
    REG_DWORD = 4

    def __init__(self):
        # {hive: {path: {name: (value, type)}}}
        self.store: dict = {}

    # -- أدوات مساعدة للاختبار --
    def seed(self, hive, path: str, name: str, value, value_type=None):
        hive = self._hive(hive)
        self.store.setdefault(hive, {}).setdefault(path, {})[name] = (
            value,
            value_type if value_type is not None else (self.REG_DWORD if isinstance(value, int) else self.REG_SZ),
        )

    def dump(self, hive, path: str) -> dict:
        return dict(self.store.get(self._hive(hive), {}).get(path, {}))

    # -- واجهة تشبه winreg --
    def OpenKey(self, hive, path, _reserved=0, _access=0):  # noqa: N802
        hive = self._hive(hive)
        if path not in self.store.get(hive, {}):
            raise FileNotFoundError(path)
        return _FakeKey(self, hive, path)

    def CreateKeyEx(self, hive, path, _reserved=0, _access=0):  # noqa: N802
        hive = self._hive(hive)
        self.store.setdefault(hive, {}).setdefault(path, {})
        return _FakeKey(self, hive, path)

    def QueryValueEx(self, key, name):  # noqa: N802
        data = self.store[key.hive][key.path]
        if name not in data:
            raise FileNotFoundError(name)
        return data[name]

    def SetValueEx(self, key, name, _reserved, value_type, value):  # noqa: N802
        self.store[key.hive][key.path][name] = (value, value_type)

    def DeleteValue(self, key, name):  # noqa: N802
        data = self.store.get(key.hive, {}).get(key.path, {})
        if name not in data:
            raise FileNotFoundError(name)
        del data[name]

    def EnumValue(self, key, index):  # noqa: N802
        items = list(self.store.get(key.hive, {}).get(key.path, {}).items())
        if index >= len(items):
            raise OSError("no more values")
        name, (value, value_type) = items[index]
        return name, value, value_type


class _FakeKey:
    def __init__(self, registry: FakeWinReg, hive, path):
        self.registry = registry
        self.hive = hive
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture()
def fake_registry():
    return FakeWinReg()
