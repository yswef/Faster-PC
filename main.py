import sys
import logging

from src.gui.main_window import launch_app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        launch_app()
    except Exception:
        # آخر خط دفاع: أي استثناء غير متوقع يُسجّل بدل ما يطبع traceback
        # خام لمستخدم غير تقني ويقفل البرنامج فجأة بدون تفسير.
        logging.exception("Fatal error, application will exit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
