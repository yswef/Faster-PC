import hashlib
import hmac
import os
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 260_000  # OWASP-recommended minimum for PBKDF2-HMAC-SHA256 (2023+)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]{3,32}$")


class AuthError(Exception):
    """خطأ متعلق بالمصادقة أو إدارة المستخدمين."""


class AuthManager:
    """
    نظام تسجيل دخول محلي بسيط (بدون خادم/شبكة) يدعم أدوارًا:
    - admin: وصول كامل (SFC/DISM، إدارة العمليات القسرية، الإعدادات، التوثيق البرمجي)
    - user: وصول للعمليات الآمنة فقط (تنظيف الملفات المؤقتة، عرض الحالة)

    ملاحظة أمنية: هذا تحكم وصول محلي على مستوى الواجهة (UX-level access control)
    لتقليل الاستخدام الخاطئ العرضي على نفس الجهاز — مو حاجز أمني ضد مهاجم يملك
    وصول فعلي لنفس حساب Windows، لأن أي شخص يقدر يعدل config.json مباشرة.
    كلمات المرور تُخزَّن كـ PBKDF2-HMAC-SHA256 مع salt عشوائي لكل مستخدم فقط،
    وما تنخزن أبدًا كنص صريح ولا بشكل قابل لعكسه.
    """

    def __init__(self, settings_manager):
        self.settings = settings_manager

    # ------------------------------------------------------------------
    @staticmethod
    def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
        if salt is None:
            salt = os.urandom(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return salt.hex(), derived.hex()

    @staticmethod
    def _validate_username(username: str):
        if not username or not USERNAME_PATTERN.match(username):
            raise AuthError(
                "اسم المستخدم يجب أن يكون 3-32 حرفًا (أحرف/أرقام/._- فقط)."
            )

    @staticmethod
    def _validate_password(password: str):
        if not password or len(password) < 8:
            raise AuthError("كلمة المرور يجب أن تكون 8 أحرف على الأقل.")

    # ------------------------------------------------------------------
    def has_any_users(self) -> bool:
        return len(self.settings.get("users") or []) > 0

    def create_user(self, username: str, password: str, role: str = "user") -> dict:
        """إنشاء مستخدم جديد. أول مستخدم يُنشأ بالتطبيق يصير admin تلقائيًا."""
        self._validate_username(username)
        self._validate_password(password)
        if role not in ("admin", "user"):
            raise AuthError("دور غير صالح.")

        users = list(self.settings.get("users") or [])
        if any(u["username"].lower() == username.lower() for u in users):
            raise AuthError("اسم المستخدم موجود مسبقًا.")

        if not users:
            role = "admin"  # أول حساب دايمًا أدمين حتى لو ما طُلب صراحة

        salt_hex, hash_hex = self._hash_password(password)
        new_user = {
            "username": username,
            "salt": salt_hex,
            "password_hash": hash_hex,
            "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        users.append(new_user)
        self.settings.set("users", users)
        logger.info(f"User created: {username} (role={role})")
        return new_user

    def authenticate(self, username: str, password: str) -> dict | None:
        """يتحقق من اسم المستخدم وكلمة المرور. يرجع بيانات المستخدم (بدون الهاش) أو None."""
        users = self.settings.get("users") or []
        for u in users:
            if u.get("username", "").lower() == username.lower():
                salt = bytes.fromhex(u["salt"])
                _, computed_hash = self._hash_password(password, salt)
                # مقارنة بزمن ثابت لتقليل خطر توقيت الهجمات (timing attack)
                if hmac.compare_digest(computed_hash, u["password_hash"]):
                    return {"username": u["username"], "role": u["role"]}
                return None
        return None

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        if self.authenticate(username, old_password) is None:
            raise AuthError("كلمة المرور الحالية غير صحيحة.")
        self._validate_password(new_password)
        users = list(self.settings.get("users") or [])
        for u in users:
            if u["username"].lower() == username.lower():
                salt_hex, hash_hex = self._hash_password(new_password)
                u["salt"], u["password_hash"] = salt_hex, hash_hex
                self.settings.set("users", users)
                logger.info(f"Password changed for user: {username}")
                return True
        return False
