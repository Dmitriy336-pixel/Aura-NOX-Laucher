"""Тексты первого запуска: условия использования и короткая инструкция, на русском и английском.
Эти тексты не проходят через i18n.tr: окно первого запуска само показывает нужный язык
и меняет его на лету, ещё до того, как язык интерфейса выбран.

AUTHOR/SOURCE (вкладка «О программе») и TERMS_AUTHOR/TERMS_SOURCE (условия) ниже заглушки: впиши своё имя и ссылку."""

from config import APP_NAME

TERMS_VERSION = "1"  # поменяй, если условия изменятся: окно с ними покажется ещё раз

# Вкладка «О программе»: строки «Автор» и «Официальный источник»
AUTHOR = {"ru": "Dmitriy336-pixel", "en": "Dmitriy336-pixel", "uk": "Dmitriy336-pixel"}
SOURCE = {"ru": "https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher",
          "en": "https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher",
          "uk": "https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher"
          }

# Условия использования: подпись автора в конце текстов лицензии
TERMS_AUTHOR = {"ru": "Dmitriy336-pixel", "en": "Dmitriy336-pixel", "uk": "Dmitriy336-pixel"}
TERMS_SOURCE = {"ru": "https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher", "en": "https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher", "uk": "https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher"}


def pick(table, lang):
    """Значение для языка; если такого языка в таблице нет, русское."""
    return table.get(lang, table["ru"])

UI = {
    "ru": {
        "language_title": "Выберите язык",
        "language_hint": "Язык можно сменить позже в настройках.",
        "terms_title": "Условия использования",
        "guide_title": "Как пользоваться",
        "next": "Далее",
        "back": "Назад",
        "start": "Начать",
        "close": "Закрыть",
        "step": "Шаг {n} из {total}",
    },
    "en": {
        "language_title": "Choose your language",
        "language_hint": "You can change the language later in the settings.",
        "terms_title": "Terms of use",
        "guide_title": "Quick guide",
        "next": "Next",
        "back": "Back",
        "start": "Get started",
        "close": "Close",
        "step": "Step {n} of {total}",
    },
}

UI["uk"] = {
    "language_title": "Виберіть мову",
    "language_hint": "Мову можна змінити пізніше в налаштуваннях.",
    "terms_title": "Умови використання",
    "guide_title": "Як користуватися",
    "next": "Далі",
    "back": "Назад",
    "start": "Почати",
    "close": "Закрити",
    "step": "Крок {n} з {total}",
}

TERMS = {
    "ru": """{app}: бесплатная программа. Прочитайте эти условия перед использованием. Если вы с ними не согласны, не используйте программу.

1. Бесплатность
Программа бесплатна. Её нельзя продавать, сдавать в аренду или распространять за плату. Нельзя просить за неё или за её изменённые версии деньги и пожертвования (донаты) в любой форме: в самой программе, на странице скачивания, в описании или в сопроводительных материалах.

2. Распространение
Каждый может свободно копировать программу и передавать её другим людям, если это бесплатно и вместе с этими условиями.

3. Изменения
Программу можно изменять и распространять изменённые версии, но только бесплатно и на этих же условиях. Изменённую версию нельзя выдавать за оригинал или за работу автора, в ней нужно прямо указать, что она изменена.

4. Что считается оригиналом
Оригинал: только версия, полученная от автора ({author}, {source}). Автор не создавал, не проверял и не отвечает ни за версии из других источников, ни за любой код, который другие люди добавили в программу, включая вредоносный (вирусы, шпионские и другие опасные программы). Если вы получили программу не от автора, вы используете её на свой риск. Скачивайте программу только из официального источника.

5. Без гарантий
Программа предоставляется «как есть», без каких-либо гарантий. Автор не отвечает за ущерб, потерю данных и другие последствия её использования.

6. Ваши действия
Лаунчер запускает программы и выполняет команды, которые вы задали сами: плитки и свои команды, в том числе команды Windows. Ответственность за то, что вы запускаете, лежит на вас.

7. Ваши данные
Плитки, настройки и заметки хранятся только на вашем компьютере. Программа сама ничего не отправляет в интернет и ничего не собирает. Команды, которые открывают сайты (например, поиск), открывают их в вашем браузере по вашему запросу.

8. Сторонние компоненты
Программа использует Python, PySide6 (Qt) и Pillow, у которых свои лицензии. Темы, звуки и иконки, которые вы добавляете, остаются собственностью их авторов.

Copyright (c) 2026 {author}""",
    "en": """{app} is free software. Please read these terms before using it. If you do not agree with them, do not use the program.

1. Free of charge
The program is free. It must not be sold, rented out or distributed for a fee. Nobody may ask for money or donations for it or for its modified versions in any form: inside the program, on a download page, in a description or in accompanying materials.

2. Distribution
Anyone may freely copy the program and pass it on to other people, provided this is free of charge and together with these terms.

3. Modifications
The program may be modified and modified versions may be distributed, but only free of charge and under these same terms. A modified version must not be presented as the original or as the author's work, and it must clearly state that it has been modified.

4. What counts as the original
The original is only the version received from the author ({author}, {source}). The author did not create, check or take responsibility for versions from other sources, or for any code that other people added to the program, including malicious code (viruses, spyware and other dangerous programs). If you received the program from anyone other than the author, you use it at your own risk. Download the program only from the official source.

5. No warranty
The program is provided "as is", without warranty of any kind. The author is not liable for damage, data loss or any other consequences of using it.

6. Your actions
The launcher starts programs and runs commands that you set up yourself: tiles and your own commands, including Windows commands. You are responsible for what you run.

7. Your data
Tiles, settings and notes are stored only on your computer. The program does not send anything to the internet and does not collect anything. Commands that open websites (for example, search) open them in your browser at your request.

8. Third-party components
The program uses Python, PySide6 (Qt) and Pillow, which have their own licenses. Themes, sounds and icons that you add remain the property of their authors.

Copyright (c) 2026 {author}""",
}

TERMS["uk"] = """{app}: безкоштовна програма. Прочитайте ці умови перед використанням. Якщо ви з ними не згодні, не користуйтеся програмою.

1. Безкоштовність
Програма безкоштовна. Її не можна продавати, здавати в оренду чи поширювати за плату. Не можна просити за неї або за її змінені версії гроші та пожертви (донати) в будь-якій формі: у самій програмі, на сторінці завантаження, в описі чи в супровідних матеріалах.

2. Поширення
Кожен може вільно копіювати програму та передавати її іншим людям, якщо це безкоштовно і разом із цими умовами.

3. Зміни
Програму можна змінювати й поширювати змінені версії, але лише безкоштовно та на цих самих умовах. Змінену версію не можна видавати за оригінал чи за роботу автора, у ній потрібно прямо вказати, що її змінено.

4. Що вважається оригіналом
Оригінал: лише версія, отримана від автора ({author}, {source}). Автор не створював, не перевіряв і не відповідає ні за версії з інших джерел, ні за будь-який код, який інші люди додали до програми, зокрема шкідливий (віруси, шпигунські та інші небезпечні програми). Якщо ви отримали програму не від автора, ви користуєтеся нею на власний ризик. Завантажуйте програму лише з офіційного джерела.

5. Без гарантій
Програма надається «як є», без жодних гарантій. Автор не відповідає за шкоду, втрату даних та інші наслідки її використання.

6. Ваші дії
Лаунчер запускає програми та виконує команди, які ви задали самі: плитки й власні команди, зокрема команди Windows. Відповідальність за те, що ви запускаєте, лежить на вас.

7. Ващі дані
Плитки, налаштування та нотатки зберігаються лише на вашому комп'ютері. Програма сама нічого не надсилає в інтернет і нічого не збирає. Команди, що відкривають сайти (наприклад, пошук), відкривають їх у вашому браузері на ваш запит.

8. Сторонні компоненти
Програма використовує Python, PySide6 (Qt) і Pillow, які мають власні ліцензії. Теми, звуки та іконки, які ви додаєте, залишаються власністю їхніх авторів.

Copyright (c) 2026 {author}"""

# Короткая инструкция: (клавиши или действие, что делает)
GUIDE = {
    "ru": [
        ("Плитка «+»", "добавить программу: выберите .exe, ярлык или .bat"),
        ("Клик или клавиша", "запустить плитку; быстрая клавиша написана на самой плитке"),
        ("Стрелки, Tab, Enter", "выбор плитки с клавиатуры; Tab переносит выбор на правую панель; Enter запускает"),
        ("Правый клик или Delete", "меню плитки: удалить, цвет, иконка"),
        ("Перетаскивание или Ctrl+стрелки", "переставить плитки; кнопка ⇅ на панели блокирует перестановку"),
        ("Правая панель", "настройки, командная строка, заметки, блокировка плиток, режим высокой производительности"),
        ("Ctrl+Alt+T", "командная строка из любой программы; команда «помощь» покажет весь список"),
        ("Ctrl+Alt+N", "заметки из любой программы"),
        ("F2", "настройки: темы, звуки, язык, горячие клавиши, фоновый режим"),
        ("Ctrl+Q", "полностью закрыть лаунчер"),
    ],
    "en": [
        ("The \"+\" tile", "add a program: pick an .exe, a shortcut or a .bat file"),
        ("Click or key", "launch a tile; its quick key is written on the tile"),
        ("Arrows, Tab, Enter", "choose a tile with the keyboard; Tab moves the selection to the sidebar; Enter launches"),
        ("Right click or Delete", "tile menu: delete, color, icon"),
        ("Drag or Ctrl+arrows", "rearrange tiles; the ⇅ button on the sidebar locks rearranging"),
        ("Sidebar", "settings, command bar, notes, tile lock, high-performance mode"),
        ("Ctrl+Alt+T", "command bar from any program; the \"помощь\" (help) command lists everything"),
        ("Ctrl+Alt+N", "notes from any program"),
        ("F2", "settings: themes, sounds, language, hotkeys, background mode"),
        ("Ctrl+Q", "quit the launcher completely"),
    ],
}


GUIDE["uk"] = [
    ("Плитка «+»", "додати програму: виберіть файл .exe, ярлик або .bat"),
    ("Клік або клавіша", "запустити плитку; швидка клавіша написана на самій плитці"),
    ("Стрілки, Tab, Enter", "вибір плитки з клавіатури; Tab переносить вибір на праву панель; Enter запускає"),
    ("Правий клік або Delete", "меню плитки: видалити, колір, іконка"),
    ("Перетягування або Ctrl+стрілки", "переставити плитки; кнопка ⇅ на панелі блокує перестановку"),
    ("Права панель", "налаштування, командний рядок, нотатки, блокування плиток, режим високої продуктивності"),
    ("Ctrl+Alt+T", "командний рядок із будь-якої програми; команда «help» покаже весь список"),
    ("Ctrl+Alt+N", "нотатки з будь-якої програми"),
    ("F2", "налаштування: теми, звуки, мова, гарячі клавіші, фоновий режим"),
    ("Ctrl+Q", "повністю закрити лаунчер"),
]


def terms_text(lang):
    lang = lang if lang in TERMS else "ru"
    return TERMS[lang].format(app=APP_NAME, author=TERMS_AUTHOR[lang], source=TERMS_SOURCE[lang])