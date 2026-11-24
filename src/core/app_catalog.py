"""
دليل التطبيقات والخدمات — يربط الأسماء الفعلية (مثل code.exe) بالأسماء الودودة
والوصف الوظيفي ومستوى الخطورة عند الإيقاف.
"""

from __future__ import annotations

APP_CATALOG: dict[str, dict[str, str]] = {
    # تطوير وبرمجة
    "code.exe": {
        "friendly_name": "محرر الأكواد فيجوال ستوديو (VS Code)",
        "description": "محرر أكواد برمجية من مايكروسوفت لكتابة وتطوير البرمجيات.",
        "category": "تطوير",
        "risk": "آمن للإيقاف",
    },
    "devenv.exe": {
        "friendly_name": "فيجوال ستوديو (Visual Studio)",
        "description": "بيئة تطوير متكاملة لبناء تطبيقات ويندوز والويب.",
        "category": "تطوير",
        "risk": "آمن للإيقاف",
    },
    "pycharm64.exe": {
        "friendly_name": "باي تشارم (PyCharm)",
        "description": "بيئة تطوير متكاملة للغة بايثون من JetBrains.",
        "category": "تطوير",
        "risk": "آمن للإيقاف",
    },
    "python.exe": {
        "friendly_name": "مفسّر بايثون (Python)",
        "description": "يشغّل سكربتات وتطبيقات لغة بايثون.",
        "category": "تطوير",
        "risk": "آمن للإيقاف",
    },
    "node.exe": {
        "friendly_name": "بيئة نود جي إس (Node.js)",
        "description": "تشغّل خوادم وأدوات جافاسكربت المحلية.",
        "category": "تطوير",
        "risk": "آمن للإيقاف",
    },
    "git.exe": {
        "friendly_name": "أداة جيت (Git)",
        "description": "نظام إدارة النسخ البرمجية.",
        "category": "تطوير",
        "risk": "آمن للإيقاف",
    },
    # متصفحات
    "chrome.exe": {
        "friendly_name": "متصفح جوجل كروم (Google Chrome)",
        "description": "متصفح ويب؛ قد يفتح عدة عمليات للتبويبات والإضافات.",
        "category": "متصفح",
        "risk": "آمن للإيقاف",
    },
    "msedge.exe": {
        "friendly_name": "متصفح مايكروسوفت إيدج (Edge)",
        "description": "متصفح الويب الافتراضي في ويندوز.",
        "category": "متصفح",
        "risk": "آمن للإيقاف",
    },
    "firefox.exe": {
        "friendly_name": "متصفح فايرفوكس (Firefox)",
        "description": "متصفح ويب مفتوح المصدر من موزيلا.",
        "category": "متصفح",
        "risk": "آمن للإيقاف",
    },
    "brave.exe": {
        "friendly_name": "متصفح بريف (Brave)",
        "description": "متصفح ويب يركز على الخصوصية ومنع الإعلانات.",
        "category": "متصفح",
        "risk": "آمن للإيقاف",
    },
    # تواصل ومكتب
    "discord.exe": {
        "friendly_name": "ديسكورد (Discord)",
        "description": "تطبيق محادثة صوتية ونصية.",
        "category": "تواصل",
        "risk": "آمن للإيقاف",
    },
    "telegram.exe": {
        "friendly_name": "تيليجرام (Telegram)",
        "description": "تطبيق مراسلة فورية.",
        "category": "تواصل",
        "risk": "آمن للإيقاف",
    },
    "whatsapp.exe": {
        "friendly_name": "واتساب (WhatsApp)",
        "description": "تطبيق المراسلة الفورية لسطح المكتب.",
        "category": "تواصل",
        "risk": "آمن للإيقاف",
    },
    "winword.exe": {
        "friendly_name": "مايكروسوفت وورد (Word)",
        "description": "محرر المستندات النصية من أوفيس.",
        "category": "مكتب",
        "risk": "آمن للإيقاف",
    },
    "excel.exe": {
        "friendly_name": "مايكروسوفت إكسل (Excel)",
        "description": "برنامج الجداول الحسابية من أوفيس.",
        "category": "مكتب",
        "risk": "آمن للإيقاف",
    },
    "powerpnt.exe": {
        "friendly_name": "مايكروسوفت باوربوينت (PowerPoint)",
        "description": "برنامج العروض التقديمية من أوفيس.",
        "category": "مكتب",
        "risk": "آمن للإيقاف",
    },
    # وسائط وألعاب
    "spotify.exe": {
        "friendly_name": "سبوتيفاي (Spotify)",
        "description": "مشغّل الموسيقى والبودكاست.",
        "category": "وسائط",
        "risk": "آمن للإيقاف",
    },
    "vlc.exe": {
        "friendly_name": "مشغّل الوسائط (VLC)",
        "description": "مشغّل فيديو وصوتيات متعدد الصيغ.",
        "category": "وسائط",
        "risk": "آمن للإيقاف",
    },
    "steam.exe": {
        "friendly_name": "منصة ستيم (Steam)",
        "description": "متجر ومنصة تشغيل الألعاب.",
        "category": "ألعاب",
        "risk": "آمن للإيقاف",
    },
    # نظام ويندوز الحرجة
    "explorer.exe": {
        "friendly_name": "مستكشف ويندوز (Windows Explorer)",
        "description": "واجهة سطح المكتب وشريط المهام وإدارة الملفات.",
        "category": "نظام",
        "risk": "حذر",
    },
    "svchost.exe": {
        "friendly_name": "مضيف خدمات ويندوز (Service Host)",
        "description": "يشغّل خدمات النظام الأساسية (الشبكة، الصوت، التحديثات). إيقافه يسبب شاشة زرقاء.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "csrss.exe": {
        "friendly_name": "نظام وقت التشغيل الفرعي (CSRSS)",
        "description": "عملية نواة أساسية في ويندوز. إنهاؤها يسبب شاشة زرقاء فورية.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "wininit.exe": {
        "friendly_name": "تهيئة ويندوز (Windows Initialization)",
        "description": "تبدأ خدمات النظام عند الإقلاع. إنهاؤها يسبب شاشة زرقاء فورية.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "winlogon.exe": {
        "friendly_name": "مدير تسجيل دخول ويندوز (Winlogon)",
        "description": "يدير جلسة المستخدم وشاشة القفل. إنهاؤه يسبب شاشة زرقاء أو خروجاً قسرياً.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "lsass.exe": {
        "friendly_name": "خدمة أمان الحسابات (LSASS)",
        "description": "تتحقق من كلمات المرور وسياسات الأمان. إنهاؤها يسبب إعادة تشغيل فورية.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "services.exe": {
        "friendly_name": "مدير التحكم بالخدمات (SCM)",
        "description": "يدير جميع خدمات ويندوز. إنهاؤه يسبب شاشة زرقاء فورية.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "smss.exe": {
        "friendly_name": "مدير الجلسات (Session Manager)",
        "description": "عملية إقلاع أساسية في نواة ويندوز. إنهاؤها يسبب شاشة زرقاء فورية.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "dwm.exe": {
        "friendly_name": "مدير نوافذ سطح المكتب (DWM)",
        "description": "يرسم النوافذ والتأثيرات البصرية على الشاشة.",
        "category": "نظام",
        "risk": "حرج للنظام",
    },
    "msmpeng.exe": {
        "friendly_name": "حماية ويندوز (Windows Defender)",
        "description": "مكافح الفيروسات المدمج في ويندوز لحماية الجهاز.",
        "category": "أمان",
        "risk": "حرج للنظام",
    },
    "spoolsv.exe": {
        "friendly_name": "خدمة الطباعة (Print Spooler)",
        "description": "تدير مهام الطباعة والطابعات المتصلة.",
        "category": "نظام",
        "risk": "حذر",
    },
    "taskmgr.exe": {
        "friendly_name": "مدير المهام (Task Manager)",
        "description": "أداة مراقبة العمليات والأداء في ويندوز.",
        "category": "نظام",
        "risk": "حذر",
    },
}

SERVICE_CATALOG: dict[str, dict[str, str]] = {
    "rpcss": {
        "friendly_name": "استدعاء الإجراءات عن بُعد (RPC)",
        "description": "خدمة أساسية للتواصل بين مكونات ويندوز. إيقافها يعطل النظام فوراً.",
        "risk": "حرج للنظام",
    },
    "dcomlaunch": {
        "friendly_name": "مشغّل خوادم DCOM",
        "description": "تشغّل خدمات النظام الأساسية. إيقافها يسبب شاشة زرقاء.",
        "risk": "حرج للنظام",
    },
    "power": {
        "friendly_name": "إدارة الطاقة (Power)",
        "description": "تدير خطط الطاقة والبطارية والسكون.",
        "risk": "حرج للنظام",
    },
    "plugplay": {
        "friendly_name": "التوصيل والتشغيل (Plug and Play)",
        "description": "تتعرف على الأجهزة المتصلة مثل USB والشاشات.",
        "risk": "حرج للنظام",
    },
    "wuauserv": {
        "friendly_name": "تحديثات ويندوز (Windows Update)",
        "description": "تتحقق من تحديثات النظام والأمان وتثبتها.",
        "risk": "حذر",
    },
    "sysmain": {
        "friendly_name": "تحسين الذاكرة المسبق (SysMain / Superfetch)",
        "description": "تسرّع فتح البرامج الشائعة؛ يمكن إيقافها على الأقراص الصلبة لتقليل استهلاك القرص.",
        "risk": "آمن للإيقاف",
    },
    "wsearch": {
        "friendly_name": "فهرسة البحث (Windows Search)",
        "description": "تفهرس الملفات لتسريع البحث؛ قد تستهلك القرص أحياناً.",
        "risk": "آمن للإيقاف",
    },
    "spooler": {
        "friendly_name": "قائمة انتظار الطباعة (Print Spooler)",
        "description": "تدير الطابعات؛ آمنة للإيقاف إذا لم تكن تستخدم طابعة.",
        "risk": "آمن للإيقاف",
    },
    "diagtrack": {
        "friendly_name": "تتبع التشخيص والقياس (Telemetry)",
        "description": "ترسل بيانات تشخيصية لمايكروسوفت.",
        "risk": "آمن للإيقاف",
    },
}


def get_process_info(name: str) -> dict[str, str]:
    key = (name or "").strip().lower()
    if key in APP_CATALOG:
        return APP_CATALOG[key]
    base = key[:-4] if key.endswith(".exe") else key
    return {
        "friendly_name": base or key or "تطبيق غير معروف",
        "description": "عملية نشطة في النظام. تحقق من مسارها واسمها قبل إنهائها.",
        "category": "تطبيق",
        "risk": "آمن للإيقاف",
    }


def get_service_info(name: str, display_name: str = "") -> dict[str, str]:
    key = (name or "").strip().lower()
    if key in SERVICE_CATALOG:
        return SERVICE_CATALOG[key]
    return {
        "friendly_name": display_name or name or "خدمة نظام",
        "description": "خدمة من خدمات ويندوز أو البرامج المثبتة.",
        "risk": "حذر",
    }


__all__ = ["APP_CATALOG", "SERVICE_CATALOG", "get_process_info", "get_service_info"]
