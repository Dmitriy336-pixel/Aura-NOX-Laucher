# dialogs.py
"""Замена tkinter.messagebox: те же вызовы, но на QMessageBox.
Окна с ошибкой и предупреждением начинаются со звука error (раньше это делал sounds.hook_messagebox)."""

from PySide6.QtWidgets import QMessageBox

import sounds


def error(parent, title, text):
    sounds.play("error")
    QMessageBox.critical(parent, title, text)


def warning(parent, title, text):
    sounds.play("error")
    QMessageBox.warning(parent, title, text)


def info(parent, title, text):
    QMessageBox.information(parent, title, text)


def ask(parent, title, text) -> bool:
    """Вопрос Да/Нет. True, если выбрали «Да»."""
    answer = QMessageBox.question(parent, title, text)
    return answer == QMessageBox.StandardButton.Yes
