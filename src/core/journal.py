"""
سجل التغييرات القابلة للتراجع (Undo).

كل عملية تغيّر شيئًا في النظام (تعطيل برنامج بدء تشغيل، إيقاف خدمة، تغيير خطة
الطاقة، تعديل ريجستري...) تُسجَّل هنا مع القيم السابقة. بعدها يقدر المستخدم من
تبويب "سجل التغييرات" يرجع أي تغيير بزر واحد.

التصميم: السجل يخزّن البيانات فقط (قابلة للحفظ JSON)، وكل موديول يسجّل
"معالج تراجع" (undo handler) لنوع تغييراته — فصل كامل بدون كود دائري.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_ENTRIES = 300


class ChangeJournal:
    """سجل تغييرات دائم، يرجع آخر التغييرات ويرجّعها (undo) عند الطلب."""

    def __init__(self, path: str):
        self.path = path
        self.entries: list[dict] = []
        self._handlers: dict[str, callable] = {}
        self._next_id = 1
        self.load()

    # ------------------------------------------------------------------
    # تسجيل المعالجات (وحدة الإصلاح/التحسين تسجّل نفسها هنا)
    # ------------------------------------------------------------------
    def register_undo_handler(self, kind: str, handler) -> None:
        """handler(entry: dict) -> tuple[bool, str]  (نجاح؟, رسالة للمستخدم)"""
        self._handlers[kind] = handler

    # ------------------------------------------------------------------
    # إضافة / قراءة
    # ------------------------------------------------------------------
    def record(self, kind: str, description: str, data: dict | None = None) -> dict:
        entry = {
            "id": self._next_id,
            "time": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "description": description,
            "data": data or {},
            "undone": False,
        }
        self._next_id += 1
        self.entries.append(entry)
        if len(self.entries) > MAX_ENTRIES:
            self.entries = self.entries[-MAX_ENTRIES:]
        self.save()
        logger.info("Journal: %s", description)
        return entry

    def latest(self, count: int = 50) -> list[dict]:
        return list(reversed(self.entries[-count:]))

    def get(self, entry_id: int) -> dict | None:
        for entry in self.entries:
            if entry["id"] == entry_id:
                return entry
        return None

    def can_undo(self, entry: dict | None) -> bool:
        if not entry or entry.get("undone"):
            return False
        return entry.get("kind") in self._handlers

    # ------------------------------------------------------------------
    # تراجع
    # ------------------------------------------------------------------
    def undo(self, entry_id: int) -> tuple[bool, str]:
        entry = self.get(entry_id)
        if entry is None:
            return False, "التغيير غير موجود في السجل."
        if entry.get("undone"):
            return False, "هذا التغيير رُجّع مسبقًا."
        handler = self._handlers.get(entry.get("kind"))
        if handler is None:
            return False, "هذا النوع من التغييرات لا يدعم التراجع التلقائي."
        try:
            ok, message = handler(entry)
        except Exception as exc:  # لا نُسقط البرنامج بسبب فشل تراجع
            logger.exception("Undo failed for entry %s", entry_id)
            return False, f"تعذر التراجع: {exc}"
        if ok:
            entry["undone"] = True
            self.save()
        return ok, message

    # ------------------------------------------------------------------
    # الحفظ الدائم
    # ------------------------------------------------------------------
    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            entries = data.get("entries") if isinstance(data, dict) else data
            if isinstance(entries, list):
                self.entries = [e for e in entries if isinstance(e, dict)]
                self._next_id = max((e.get("id", 0) for e in self.entries), default=0) + 1
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            logger.warning("Could not read change journal (%s); starting empty.", exc)
            self.entries = []

    def save(self) -> bool:
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".journal_", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump({"entries": self.entries}, fh, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
            return True
        except OSError as exc:
            logger.error("Could not save change journal: %s", exc)
            return False

    def clear(self) -> None:
        self.entries = []
        self.save()


__all__ = ["ChangeJournal", "MAX_ENTRIES"]
