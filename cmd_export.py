"""Экспорт и импорт своих команд пользователя в/из JSON-файла (диалоги на Qt)."""
import json

from PySide6.QtWidgets import QFileDialog

import dialogs
import user_commands
from i18n import tr


def _parent(app):
    """Родитель для диалогов: главное окно, если оно на виду (иначе диалог был бы привязан к спрятанному окну)."""
    try:
        return app if app.isVisible() and not app.isMinimized() else None
    except RuntimeError:
        return None


def export_commands(app):
    """Диалог «Сохранить как…» и запись своих команд в файл."""
    parent = _parent(app)
    entries = user_commands.load()
    if not entries:
        dialogs.info(parent, tr("Экспорт"), tr("Своих команд нет — экспортировать нечего."))
        return False
    path, _ = QFileDialog.getSaveFileName(
        parent, tr("Экспорт своих команд"), "launcher_commands.json",
        f"{tr('Файл команд')} (*.json);;{tr('Все файлы')} (*.*)")
    if not path:
        return False
    if not path.lower().endswith(".json") and "." not in path.replace("\\", "/").rsplit("/", 1)[-1]:
        path += ".json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except OSError as e:
        dialogs.error(parent, tr("Экспорт"), str(e))
        return False
    dialogs.info(parent, tr("Экспорт"), tr("Сохранено: {n} команд в {path}", n=len(entries), path=path))
    return True


def import_commands(app):
    """Диалог «Открыть…» и добавление команд из файла к уже существующим (дубли пропускаются)."""
    parent = _parent(app)
    path, _ = QFileDialog.getOpenFileName(
        parent, tr("Импорт своих команд"), "",
        f"{tr('Файл команд')} (*.json);;{tr('Все файлы')} (*.*)")
    if not path:
        return False
    try:
        with open(path, encoding="utf-8-sig") as f:
            new_entries = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        dialogs.error(parent, tr("Импорт"), str(e))
        return False
    if not isinstance(new_entries, list):
        dialogs.error(parent, tr("Импорт"), tr("Неверный формат файла."))
        return False

    existing = user_commands.load()
    taken = {n for e in existing for n in e.get("names", [])} | set(getattr(app.registry, "builtin_names", ()))
    added = skipped = 0
    for entry in new_entries:
        names = entry.get("names") if isinstance(entry, dict) else None
        valid = (isinstance(names, list) and names and all(isinstance(n, str) for n in names)
                 and entry.get("target") and entry.get("action") in user_commands.ACTIONS)
        if not valid:
            skipped += 1
            continue
        names = [n.lower() for n in names]
        if any(n in taken for n in names):  # имя уже занято своей или встроенной командой
            skipped += 1
            continue
        entry["names"] = names
        existing.append(entry)
        taken.update(names)
        added += 1

    if added == 0:
        dialogs.info(parent, tr("Импорт"), tr("Новых команд не найдено (все уже есть или файл пустой)."))
        return False
    try:
        user_commands.save(existing)
    except OSError as e:
        dialogs.error(parent, tr("Импорт"), str(e))
        return False
    app.reload_commands()  # новые команды сразу доступны в командной строке
    try:
        app.refresh_settings_window()  # и в списке на странице «Команды» в настройках
    except Exception:
        pass
    msg = tr("Добавлено: {added}", added=added)
    if skipped:
        msg += tr(", пропущено дублей: {skipped}", skipped=skipped)
    dialogs.info(parent, tr("Импорт"), msg)
    return True
