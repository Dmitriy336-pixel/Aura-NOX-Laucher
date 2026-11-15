"""Основа командной строки: описание команд и разбор введённого текста.
Сами команды лежат в builtin_commands.py.

Обработчик команды получает текст после имени и возвращает:
  None     - всё сделано, строка закроется;
  Reply    - ответ (обычный или ошибка), строка останется открытой; обычная строка тоже считается ответом;
  Paged    - многостраничный ответ (листается клавишами PgUp / PgDn).

Необязательная функция complete(текст после имени) возвращает подсказки по аргументам
в виде списка (что подставить, короткая метка, описание): так число столов и список окон
подстраиваются под то, что есть сейчас, и не нужно прописывать «рб 1», «рб 2», «рб 3»..."""
from dataclasses import dataclass
from i18n import tr


@dataclass
class Command:
    names: list         # все варианты написания; первое имя главное
    description: str
    handler: object     # handler(args: str)
    complete: object = None


@dataclass
class Reply:
    text: str
    error: bool = False


@dataclass
class Paged:
    title: str
    lines: list         # строки вида (список имён, описание)
    per_page: int = 5   # строк на странице
    page: int = 0       # с какой страницы начать (с нуля)


class CommandRegistry:
    def __init__(self):
        self.commands = []
        self.builtin_names = set()  # имена встроенных команд: их нельзя занять своими
        

    def add(self, names, description, handler, complete=None):
        self.commands.append(Command([n.lower() for n in names], description, handler, complete))
        

    def find(self, word):
        """Команда, у которой слово совпало с одним из имён целиком."""
        word = word.lower()
        for cmd in self.commands:
            if word in cmd.names:
                return cmd
        return None

    def suggest(self, word):
        """Команды, имя которых начинается с введённого. Список пар (команда, подходящее имя)."""
        word = word.lower()
        found = []
        for cmd in self.commands:
            for name in cmd.names:
                if name.startswith(word):
                    found.append((cmd, name))
                    break
        return found

    def complete(self, cmd, args):
        """Подсказки по аргументам команды; если функция сломалась, просто без подсказок."""
        if cmd.complete is None:
            return []
        try:
            return cmd.complete(args)
        except Exception:
            return []

    def run(self, text):
        word, _, args = text.strip().partition(" ")
        cmd = self.find(word)
        if cmd is None:
            return Reply(tr('Неизвестная команда: {word}. Введи «помощь»', word=word), error=True)
        try:
            return cmd.handler(args.strip())
        except Exception as e:  # ошибка в одной команде не должна ронять лаунчер
            return Reply(tr('Ошибка: {e}', e=e), error=True)