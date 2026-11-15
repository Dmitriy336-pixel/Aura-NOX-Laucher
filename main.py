"""Точка входа. Запуск: python main.py"""
import ctypes
import os
import sys

from single_instance import SingleInstance

if __name__ == "__main__":
    
    instance = SingleInstance()
    if "--restart" in sys.argv:
        # перезапуск из настроек: ждём, пока прежний экземпляр закроется, иначе он сочтёт нас вторым
        import time
        for _ in range(30):
            if not instance.already_running:
                break
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(instance.handle))  # иначе объект не исчезнет
            time.sleep(0.3)
            instance = SingleInstance()
    if instance.already_running:
        # лаунчер уже работает: показываем его и выходим
        # (при автозапуске с --background ничего показывать не нужно)
        if "--background" not in sys.argv:
            instance.signal_existing()
        sys.exit()

    import customtkinter as ctk
    import i18n
    import storage

    # язык задаётся до импорта остальных модулей: часть текстов собирается при импорте
    boot_settings = storage.load_settings()
    ctk.set_appearance_mode(boot_settings.get("theme_mode", "dark"))
    if "--background" not in sys.argv:
        import firstrun
        if firstrun.needed(boot_settings):  # первый запуск: язык, условия, инструкция
            firstrun.run(boot_settings)
    i18n.set_language(boot_settings.get("language", i18n.DEFAULT))

    from app import App
    import keyfix
    
    # собственный идентификатор программы: панель задач берёт иконку окна, а не питоновскую
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TileLauncher.App")

    ctk.set_appearance_mode("dark")
    # --background передаёт автозапуск: стартуем сразу спрятанными
    app = App(start_hidden="--background" in sys.argv)
    
    keyfix.install(app)  # Ctrl+V, C, X, A работают и на русской раскладке
    
    # сигнал от второго экземпляра приходит из другого потока, поэтому передаём через after
    instance.listen(lambda: app.after(0, app.show_window))
        # собранный exe прописывает в окружение пути к своей временной папке (TCL_LIBRARY, TK_LIBRARY);
    # программы, запущенные плитками, унаследовали бы их и не нашли свои Tcl/Tk
    for name in ("TCL_LIBRARY", "TK_LIBRARY"):
        os.environ.pop(name, None)
    app.mainloop()
    os._exit(0)  # цикл закончился: завершаем процесс сразу, чтобы не остаться невидимым и не мешать новому запуску