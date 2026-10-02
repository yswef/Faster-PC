"""
بديل مبسّط لوحدة winreg على الأنظمة غير ويندوز.

سببه: كود المشروع يستورد winreg في الأعلى (طبيعي لتطبيق ويندوز)، وهذا يمنع
تشغيل الفحوصات والاختبارات على أي نظام آخر. هذا الملف يعطي نفس الأسماء، وكل
دالة هنا ترفع OSError متوقعة يتعامل معها الكود أصلًا — فلا يتغير سلوك البرنامج
على ويندوز إطلاقًا.
"""

from __future__ import annotations


class _UnsupportedRegistryError(OSError):
    def __init__(self) -> None:
        super().__init__("الريجستري غير متوفر على هذا النظام (ويندوز فقط).")


HKEY_CLASSES_ROOT = 0x80000000
HKEY_CURRENT_USER = 0x80000001
HKEY_LOCAL_MACHINE = 0x80000002
HKEY_USERS = 0x80000003
HKEY_CURRENT_CONFIG = 0x80000005

KEY_QUERY_VALUE = 0x0001
KEY_SET_VALUE = 0x0002
KEY_CREATE_SUB_KEY = 0x0004
KEY_ENUMERATE_SUB_KEYS = 0x0008
KEY_READ = 0x20019
KEY_WRITE = 0x20006
KEY_ALL_ACCESS = 0xF003F

REG_SZ = 1
REG_EXPAND_SZ = 2
REG_BINARY = 3
REG_DWORD = 4
REG_QWORD = 11
REG_MULTI_SZ = 7

HKEY_PERFORMANCE_DATA = 0x80000004


def _unsupported(*_args, **_kwargs):
    raise _UnsupportedRegistryError()


OpenKey = _unsupported
CreateKey = _unsupported
CreateKeyEx = _unsupported
QueryValueEx = _unsupported
SetValueEx = _unsupported
DeleteValue = _unsupported
EnumValue = _unsupported
EnumKey = _unsupported
QueryInfoKey = _unsupported
DeleteKey = _unsupported
CloseKey = _unsupported
OpenKeyEx = _unsupported
ConnectRegistry = _unsupported
FlushKey = _unsupported
ExpandEnvironmentStrings = _unsupported
SaveKey = _unsupported
LoadKey = _unsupported

__all__ = [name for name in dir() if not name.startswith("_")]
__all__.append("_UnsupportedRegistryError")
