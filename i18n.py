# i18n.py
"""Язык интерфейса.
Русские строки в коде — ключи. tr("текст") ищет перевод в таблице языка,
при отсутствии возвращает русский текст.

    from i18n import tr
    tr("Настройки")               -> "Settings" на английском
    tr("Удалить «{name}»?", name=title) -> подстановка значений

Не зависит от GUI-фреймворка."""

LANGS = {"ru": "Русский", "en": "English", "uk": "Українська"}
DEFAULT = "ru"

_lang = DEFAULT
_tables: dict = {}
missing: set = set()


def set_language(code: str) -> None:
    global _lang
    _lang = code if code in LANGS else DEFAULT


def language() -> str:
    return _lang


def language_name(code: str, ui: str = None) -> str:
    ui = ui or _lang
    if code == "ru" and ui != "ru":
        return "Ru"
    return LANGS.get(code, code)


def _table(code: str) -> dict:
    if code not in _tables:
        try:
            module = __import__(f"lang_{code}")
            _tables[code] = getattr(module, code.upper(), {})
        except ImportError:
            _tables[code] = {}
    return _tables[code]


def tr(text: str, **values) -> str:
    if _lang != DEFAULT:
        translated = _table(_lang).get(text)
        if translated is None:
            missing.add(text)
        else:
            text = translated
    return text.format(**values) if values else text
