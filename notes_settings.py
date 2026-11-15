"""Блок «Хранение» в разделе «Заметки» настроек: где лежат заметки, смена папки с переносом, открыть папку."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

import theme
from notes_store import NoteStore, default_dir
from i18n import tr


class NotesFolderPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=480, text_color=theme.DIM,
            text=tr("Заметки это обычные файлы .md в одной папке: их можно открыть и в других программах. "
                 "При смене папки лаунчер предложит скопировать в неё уже существующие заметки."),
        ).pack(fill="x", padx=8, pady=(0, 6))
        self.path_label = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=480)
        self.path_label.pack(fill="x", padx=10, pady=(0, 8))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=8)
        ctk.CTkButton(row, text=tr("Выбрать папку…"), width=150, command=self.choose).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text=tr("Открыть"), width=100, command=self.open_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text=tr("По умолчанию"), width=130, command=self.reset).pack(side="left")
        self.show()

    def current(self):
        return self.app.settings.get("notes_dir") or default_dir()

    def show(self):
        self.path_label.configure(text=self.current())

    def switch_to(self, folder):
        """Меняет папку; если в прежней есть заметки, предлагает скопировать их в новую."""
        top = self.winfo_toplevel()
        old = self.current()
        if folder is not None and os.path.normcase(os.path.abspath(folder)) == os.path.normcase(os.path.abspath(old)):
            return
        target = folder if folder is not None else default_dir()
        try:
            old_notes = NoteStore(old).list_notes()
        except OSError:
            old_notes = []
        if old_notes and messagebox.askyesno(
                tr("Заметки"), tr('Скопировать заметки ({v}) из прежней папки в новую?\nОдноимённые заметки в новой папке не будут перезаписаны.', v=len(old_notes)), parent=top):
            try:
                copied, skipped = NoteStore(old).copy_notes_to(target)
            except OSError as e:
                messagebox.showerror(tr("Заметки"), tr('Не удалось скопировать:\n{e}', e=e), parent=top)
                return
            if skipped:
                messagebox.showinfo(tr("Заметки"), tr('Скопировано: {copied}. Пропущено одноимённых: {skipped}.', copied=copied, skipped=skipped), parent=top)
        if self.app.change_notes_dir(folder):
            self.show()

    def choose(self):
        folder = filedialog.askdirectory(parent=self.winfo_toplevel(), title=tr("Папка для заметок"), initialdir=self.current())
        if folder:
            self.switch_to(os.path.normpath(folder))

    def reset(self):
        self.switch_to(None)

    def open_folder(self):
        try:
            os.makedirs(self.current(), exist_ok=True)
            os.startfile(self.current())  # только Windows
        except (OSError, AttributeError) as e:
            messagebox.showerror(tr("Заметки"), tr('Не удалось открыть папку:\n{v}\n\n{e}', v=self.current(), e=e),
                                 parent=self.winfo_toplevel())