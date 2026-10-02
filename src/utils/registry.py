"""
وصول آمن للريجستري — كل قراءة/كتابة تمر من هنا.

الهدف: مكان واحد يتعامل مع غياب winreg (أنظمة غير ويندوز) بدل تكرار
try/ImportError في كل ملف، مع رسائل واضحة وصلاحيات محددة.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:  # ويندوز
    import winreg  # type: ignore
    _AVAILABLE = True
except ImportError:  # أنظمة أخرى — بديل آمن
    from src.utils import winreg_stub as winreg  # type: ignore

    _AVAILABLE = False


def registry_available() -> bool:
    return _AVAILABLE


def read_value(root, key_path: str, name: str, default=None):
    """قراءة قيمة من الريجستري؛ ترجع default لو ما وُجدت أو تعذّرت القراءة."""
    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except (OSError, FileNotFoundError, PermissionError):
        return default


def write_value(root, key_path: str, name: str, value, value_type=None) -> bool:
    """كتابة قيمة DWORD/نص. ترجع True عند النجاح."""
    if not _AVAILABLE:
        logger.info("Registry write skipped (not Windows): %s\\%s", key_path, name)
        return False
    if value_type is None:
        value_type = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
    try:
        with winreg.CreateKeyEx(root, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as key:
            winreg.SetValueEx(key, name, 0, value_type, value)
        return True
    except PermissionError:
        logger.warning("Registry write denied (run as Administrator): %s\\%s", key_path, name)
        return False
    except OSError as exc:
        logger.warning("Registry write failed %s\\%s: %s", key_path, name, exc)
        return False


def delete_value(root, key_path: str, name: str) -> bool:
    """حذف قيمة من الريجستري. ترجع True عند النجاح أو عدم وجودها."""
    if not _AVAILABLE:
        return False
    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        logger.warning("Registry delete failed %s\\%s: %s", key_path, name, exc)
        return False


def enum_values(root, key_path: str) -> list[tuple[str, object, int]]:
    """قراءة كل قيم مفتاح: قائمة (الاسم، القيمة، النوع). فاضية لو تعذّرت القراءة."""
    items: list[tuple[str, object, int]] = []
    if not _AVAILABLE:
        return items
    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ) as key:
            index = 0
            while True:
                try:
                    name, value, vtype = winreg.EnumValue(key, index)
                    items.append((name, value, vtype))
                    index += 1
                except OSError:
                    break
    except (FileNotFoundError, PermissionError):
        pass
    except OSError as exc:
        logger.debug("Could not enumerate %s: %s", key_path, exc)
    return items


def key_exists(root, key_path: str) -> bool:
    if not _AVAILABLE:
        return False
    try:
        with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ):
            return True
    except OSError:
        return False


__all__ = ["winreg", "registry_available", "read_value", "write_value", "delete_value", "enum_values", "key_exists"]
