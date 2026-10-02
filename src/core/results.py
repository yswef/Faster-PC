"""
نتيجة موحّدة لأي عملية في البرنامج.

كل دوال النواة (تنظيف/تحسين/تحسينات/إصلاح) ترجع ActionResult، فتعرض الواجهة
النتيجة بشكل واحد ثابت (نجاح/تحذير/خطأ) بدون كود خاص لكل عملية.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActionResult:
    success: bool
    message: str
    details: str = ""
    data: dict = field(default_factory=dict)
    needs_restart: bool = False

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:  # pragma: no cover
        return f"ActionResult(success={self.success}, message={self.message!r})"


__all__ = ["ActionResult"]
