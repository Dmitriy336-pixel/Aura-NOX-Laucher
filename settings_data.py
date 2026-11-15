import i18n
from i18n import tr
"""Структура настроек: отделы -> категории -> подкатегории.
Подкатегория: строка (пока заглушка) или словарь с управлением:
  {"title": ..., "key": ..., "type": "switch"}                      переключатель
  {"title": ..., "key": ..., "type": "choice", "options": {...}}    выбор из вариантов
  {"title": ..., "key": ..., "type": "slider", "min": ..., "max": ..., "step": ..., "unit": ...}  ползунок
  {"title": ..., "key": ..., "type": "hotkey"}                      кнопка смены горячей клавиши
  необязательно "hint": текст подсказки, она всплывает по знаку «?».
Подкатегория {"custom": "..."} рисуется отдельным кодом (settings_window.draw_item): список быстрых клавиш,
справочник клавиш, цвета плиток.
Отдел с "custom" вместо "categories" рисуется отдельным кодом (сейчас так устроены «Команды»)."""

SETTINGS = [
    {
        "title": tr("Общие"),
        "categories": [
            {
                "title": tr("Язык"),
                "subcategories": [
                    {"title": tr("Язык интерфейса / Interface language"), "key": "language", "type": "choice",
                     "options": {code: i18n.language_name(code) for code in i18n.LANGS},
                     "hint": tr("Применится после перезапуска. / Applies after a restart.")},
                ],
            },
            {
                "title": tr("Запуск"),
                "subcategories": [
                    {"title": tr("Автозапуск с Windows"), "key": "autostart", "type": "switch"},
                    {
                        "title": tr("Фоновый режим"), "key": "background_mode", "type": "switch",
                        "hint": tr("Лаунчер прячется полностью и вызывается только горячей клавишей. "
                                "Полностью закрыть: Ctrl+Q."),
                    },
                ],
            },
            {
                "title": tr("Поведение"),
                "subcategories": [
                    {
                        "title": tr("После запуска программы"), "key": "after_launch", "type": "choice",
                        "options": {"minimize": tr("Свернуть"), "background": tr("В фон"), "close": tr("Закрыть")},
                        "hint": tr("«В фон» работает только при включённом фоновом режиме."),
                    },
                    {"title": tr("Подтверждать удаление плитки"), "key": "confirm_delete", "type": "switch"},
                ],
            },
            {
                "title": tr("Звуки"),
                "subcategories": [
                    {"title": tr("Звуки событий"), "key": "sounds_enabled", "type": "switch",
                     "hint": tr("Файлы .wav или .mp3 кладутся в папку sounds рядом с программой. Имя файла задаёт событие, "
                             "полный список лежит в папке в файле имена_звуков.txt. Нет файла: нет звука.")},
                    {"title": tr("Громкость звуков"), "key": "sound_volume", "type": "slider",
                     "min": 0, "max": 100, "step": 5, "unit": "%",
                     "hint": tr("Это громкость звуков лаунчера, системную она не меняет.")},
                ],
            },
            {
                "title": tr("Окно"),
                "subcategories": [
                    {
                        "title": tr("Размер окна при запуске"), "key": "window_scale", "type": "slider",
                        "min": 40, "max": 100, "step": 5, "unit": "%",
                        "hint": tr("Применится при следующем запуске."),
                    },
                ],
            },
        ],
    },
    {
        "title": tr("Управление"),
        "categories": [
            {
                "title": tr("Горячие клавиши"),
                "subcategories": [
                    {
                        "title": tr("Вызов лаунчера из фона"), "key": "hotkey_summon", "type": "hotkey",
                        "hint": tr("Работает при включённом фоновом режиме. Нажатие показывает или прячет лаунчер."),
                    },
                    {
                        "title": tr("Вызов командной строки"), "key": "hotkey_command", "type": "hotkey",
                        "hint": tr("Работает из любой программы, пока командная строка включена."),
                    },
                    {
                        "title": tr("Командная строка"), "key": "command_line", "type": "switch",
                        "hint": tr("Кнопка «>_» на панели и вызов горячей клавишей ниже. "
                        "Команда «помощь» покажет список команд."),
                    },
                ],
            },
            {"title": tr("Быстрые клавиши плиток"), "subcategories": [{"custom": "tile_keys"}]},
            {"title": tr("Клавиши внутри лаунчера"), "subcategories": [{"custom": "shortcuts"}]},
        ],
    },
    {"title": tr("Команды"), "custom": "commands"},  # страница со своими командами (commands_page.py)
    {
        "title": tr("Заметки"),
        "categories": [
            {
                "title": tr("Открытие"),
                "subcategories": [
                    {"title": tr("Открывать заметки горячей клавишей"), "key": "notes_hotkey", "type": "switch",
                     "hint": tr("Работает из любой программы: окно заметок появится рядом с кнопкой на панели, "
                             "а если лаунчер спрятан, по центру экрана.")},
                    {"title": tr("Горячая клавиша заметок"), "key": "hotkey_notes", "type": "hotkey"},
                ],
            },
            {
                "title": tr("Редактор"),
                "subcategories": [
                    {"title": tr("Размер шрифта"), "key": "notes_font_size", "type": "slider",
                     "min": 10, "max": 28, "step": 1, "unit": " px"},
                    {"title": tr("Автосохранение через"), "key": "notes_autosave_ms", "type": "slider",
                     "min": 300, "max": 3000, "step": 100, "unit": tr(" мс"),
                     "hint": tr("Сколько ждать после последней правки, прежде чем записать заметку на диск.")},
                    {"title": tr("Порядок заметок в списке"), "key": "notes_sort", "type": "choice",
                     "options": {"date": tr("Сначала новые"), "name": tr("По алфавиту")}},
                ],
            },
            {"title": tr("Хранение"), "subcategories": [{"custom": "notes_folder"}]},
        ],
    },
    {
        "title": tr("Внешний вид"),
        "categories": [
            {
                "title": tr("Плитки"),
                "subcategories": [
                    {"title": tr("Плиток в строке"), "key": "columns", "type": "slider",
                     "min": 2, "max": 10, "step": 1},
                    {"title": tr("Максимальный размер плитки"), "key": "max_tile_size", "type": "slider",
                     "min": 60, "max": 200, "step": 10, "unit": " px"},
                    {"title": tr("Размер иконки на плитке"), "key": "tile_icon_size", "type": "slider",
                     "min": 30, "max": 90, "step": 5, "unit": "%",
                     "hint": tr("Работает, когда название внутри плитки. В остальных режимах иконка занимает почти всю плитку.")},
                    {"title": tr("Где показывать название плитки"), "key": "tile_label", "type": "choice",
                     "options": {"inside": tr("На плитке"), "below": tr("Под плиткой"), "hover": tr("При наведении")},
                     "hint": tr("У плиток без иконки название всегда на самой плитке. "
                             "При «Под плиткой» и «При наведении» иконка занимает почти всю плитку.")},
                    {"title": tr("Показывать быструю клавишу на плитке"), "key": "tile_show_key", "type": "switch"},
                ],
            },
            {"title": tr("Цвета плиток"), "subcategories": [{"custom": "tile_colors"}]},
            {
                "title": tr("Панель"),
                "subcategories": [
                    {"title": tr("Ширина панели"), "key": "sidebar_width", "type": "slider",
                     "min": 64, "max": 160, "step": 8, "unit": " px"},
                    {"title": tr("Кнопка заметок"), "key": "show_notes_btn", "type": "switch"},
                    {"title": tr("Кнопка блокировки плиток"), "key": "show_lock_btn", "type": "switch",
                     "hint": tr("Если спрятать кнопку, плитки останутся в том состоянии, в каком были: "
                             "закреплёнными или свободными.")},
                    {"title": tr("Кнопка режима производительности"), "key": "show_perf_btn", "type": "switch"},
                ],
            },
            {
            "title": tr("Иконки плиток"),
            "subcategories": [
                    {"title": tr("Подбирать иконку при добавлении"), "key": "auto_icons", "type": "switch",
                     "hint": tr("Новая плитка сама получает иконку: из папки готовых иконок или из самой программы.")},
                    {"custom": "icons"},
                ],
            },
        ],
    },
    {
        "title": tr("Темы"),
        "categories": [
            {
                "title": tr("Режим"),
                "subcategories": [
                    {"title": tr("Оформление"), "key": "theme_mode", "type": "choice",
                     "options": {"dark": tr("Тёмная"), "light": tr("Светлая"), "system": tr("Как в Windows")},
                     "hint": tr("«Как в Windows» следует за системной темой и меняется вместе с ней.")},
                ],
            },
            {"title": tr("Темы оформления"), "subcategories": [{"custom": "theme_pack"}]},
        ],
    },
    {"title": tr("FAQ"), "custom": "faq"},  # вопросы и ответы (faq_page.py, faq_data.py)
    {"title": tr("О программе"), "custom": "about"},  # страница с автором, условиями и сведениями (about_page.py)
]
