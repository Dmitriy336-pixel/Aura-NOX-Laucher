# main.py
"""Точка входа. Запуск: python main.py"""

import os
import sys

# Убираем переменные Tcl/Tk из окружения (если остались от старой версии)
for _name in ("TCL_LIBRARY", "TK_LIBRARY"):
    os.environ.pop(_name, None)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from single_instance import SingleInstance


def main():
    # ── Защита от второго экземпляра ────────────────────────────────────
    instance = SingleInstance()

    if "--restart" in sys.argv:
        # ждём, пока закроется предыдущий экземпляр (до 3 сек)
        import time
        for _ in range(10):
            if not instance.already_running:
                break
            instance.close_handle()
            time.sleep(0.3)
            instance = SingleInstance()

    if instance.already_running:
        if "--background" not in sys.argv:
            instance.signal_existing()
        sys.exit(0)

    # ── Создаём QApplication ─────────────────────────────────────────────
    # Включаем High DPI (в PySide6 6.4+ это дефолт, но явно не помешает)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("Aura NOX Launcher")
    app.setOrganizationName("AuraNOX")

    # Идентификатор для панели задач Windows (иконка окна, а не Python)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "TileLauncher.App")
    except (AttributeError, OSError):
        pass

    # ── Загружаем настройки и язык ───────────────────────────────────────
    import storage
    import i18n

    boot_settings = storage.load_settings()
    i18n.set_language(boot_settings.get("language", i18n.DEFAULT))

    # ── Применяем тему (QApplication уже существует) ─────────────────────
    import theme
    theme.apply(
        name=boot_settings.get("theme_name", theme.DEFAULT_NAME),
        mode=boot_settings.get("theme_mode", "dark"),
        app=app,
    )

    # Иконка приложения
    from config import ICON_PATH
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    # ── Первый запуск: язык, условия, инструкция ─────────────────────────
    if "--background" not in sys.argv:
        import firstrun
        if firstrun.needed(boot_settings):
            firstrun.run(boot_settings)
            # После мастера язык и terms_seen уже сохранены в файл,
            # перечитываем чтобы получить выбранный язык
            boot_settings = storage.load_settings()
            i18n.set_language(boot_settings.get("language", i18n.DEFAULT))
            # Переприменяем тему на случай если firstrun изменил settings
            theme.apply(app=app)

    # ── Инициализируем звуки ─────────────────────────────────────────────
    import sounds
    sounds.init(boot_settings)

    # ── Главное окно ─────────────────────────────────────────────────────
    from app import App
    window = App(settings=boot_settings,
                 start_hidden="--background" in sys.argv)

    # Сигнал от второго экземпляра → показать окно
    instance.listen(lambda: window.show_window_from_signal())

    # ── Запуск цикла событий ─────────────────────────────────────────────
    exit_code = app.exec()

    # Гарантированно завершаем процесс
    os._exit(exit_code)


if __name__ == "__main__":
    main()
