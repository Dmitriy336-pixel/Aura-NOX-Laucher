"""Язык интерфейса. Исходные строки в коде русские, поэтому русский язык это сами строки без изменений,
а английский берётся из таблицы lang_en.py (ключ = русская строка).

    from i18n import tr
    tr("Настройки")                          -> "Settings" на английском, "Настройки" на русском
    tr("Удалить «{name}»?", name=title)      -> подстановка значений в {}

Нет строки в таблице: показывается русский текст (программа не падает, а пропуск легко найти).
Язык выбирается один раз при запуске (settings.json, ключ language), смена языка включается перезапуском."""
LANGS = {"ru": "Русский", "en": "English", "uk": "Українська"}  # код языка -> название на нём самом
DEFAULT = "ru"

_lang = DEFAULT
_tables = {}
missing = set()  # строки без перевода, которые просили на этом языке (для проверки полноты перевода)


def set_language(code):
    global _lang
    _lang = code if code in LANGS else DEFAULT


def language():
    return _lang


def language_name(code, ui=None):
    """Название языка в списке выбора. Русский на украинском и английском интерфейсе подписан просто «Ru»,
    на русском остаётся «Русский»; остальные языки подписаны на себе самих."""
    ui = ui or _lang
    if code == "ru" and ui != "ru":
        return "Ru"
    return LANGS.get(code, code)


def _table(code):
    if code not in _tables:
        try:
            module = __import__(f"lang_{code}")
            _tables[code] = getattr(module, code.upper(), {})
        except ImportError:
            _tables[code] = {}
    return _tables[code]


def tr(text, **values):
    if _lang != DEFAULT:
        translated = _table(_lang).get(text)
        if translated is None:
            missing.add(text)
        else:
            text = translated
    return text.format(**values) if values else text
