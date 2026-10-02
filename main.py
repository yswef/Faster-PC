"""
Faster PC — نقطة التشغيل.

الاستخدام:
    python main.py               # تشغيل عادي (يفتح الإعداد الأولي عند أول مرة)
    python main.py --minimized   # التشغيل مصغّرًا في شريط المهام (يُستخدم مع التشغيل التلقائي)
    python main.py --headless    # فحص سريع بدون واجهة (للتشخيص والاختبارات)
"""

import sys


def main() -> int:
    argv = sys.argv[1:]
    if "--headless" in argv:
        from src.gui.app import run_headless_check

        return run_headless_check()

    from src.gui.app import launch_app

    return launch_app(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
