"""Страница «Команды» в настройках: список своих команд и окно создания и правки."""
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

import theme
import user_commands as uc
from i18n import tr

ACCENT = theme.ACCENT
DIM = theme.DIM
ERROR = theme.ERROR
HINTS = {
    "open": tr("Один путь или адрес сайта. {} подставит текст, введённый после команды."),
    "set": tr("По одному пути или адресу в строке: всё откроется по очереди."),
    "shell": tr("Команда командной строки Windows, выполняется без окна. {} подставит текст после команды."),
}


class CommandsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=480, text_color=DIM,
            text=tr("Свои команды для командной строки: открывают программы, папки и сайты или "
                 "выполняют команды. Пример: команда «ютуб» с адресом "
                 "https://www.youtube.com/results?search_query={} ищет на YouTube то, что напишешь дальше."),
        ).pack(fill="x", padx=8, pady=(0, 10))
        ctk.CTkButton(self, text=tr("Новая команда"), command=self.add).pack(anchor="w", padx=8, pady=(0, 8))
        self.list = ctk.CTkFrame(self, fg_color="transparent")
        self.list.pack(fill="x")
        self.render()

    def render(self):
        for child in self.list.winfo_children():
            child.destroy()
        entries = uc.load()
        if not entries:
            ctk.CTkLabel(self.list, text=tr("Пока нет своих команд."), text_color=DIM).pack(anchor="w", padx=8, pady=8)
        for index, entry in enumerate(entries):
            row = ctk.CTkFrame(self.list, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row, text=", ".join(entry["names"]), text_color=ACCENT, anchor="w",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(
                row, text=f'{uc.ACTIONS.get(entry["action"], "?")}: {uc.summary(entry)}', text_color=DIM,
                anchor="w", justify="left", wraplength=330,
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
            ctk.CTkButton(row, text=tr("Изменить"), width=80, height=28,
                          command=lambda i=index: self.edit(i)).grid(row=0, column=1, rowspan=2, padx=(0, 6))
            ctk.CTkButton(row, text=tr("Удалить"), width=80, height=28, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
                          command=lambda i=index: self.delete(i)).grid(row=0, column=2, rowspan=2, padx=(0, 10))

    def add(self):
        CommandEditor(self.winfo_toplevel(), self.app, None, self.saved)

    def edit(self, index):
        CommandEditor(self.winfo_toplevel(), self.app, index, self.saved)

    def delete(self, index):
        entries = uc.load()
        names = ", ".join(entries[index]["names"])
        if not messagebox.askyesno(tr("Удаление команды"), tr('Удалить команду «{names}»?', names=names), parent=self.winfo_toplevel()):
            return
        del entries[index]
        uc.save(entries)
        self.saved()

    def saved(self):
        self.app.reload_commands()  # командная строка сразу узнаёт об изменениях
        if self.winfo_exists():
            self.render()


class CommandEditor(ctk.CTkToplevel):
    def __init__(self, master, app, index, on_saved):
        super().__init__(master)
        self.app, self.index, self.on_saved = app, index, on_saved
        entries = uc.load()
        entry = entries[index] if index is not None else {"names": [], "description": "", "action": "open", "target": ""}
        self.other_names = {n for i, e in enumerate(entries) if i != index for n in e["names"]}

        self.title(tr("Новая команда") if index is None else tr("Правка команды"))
        self.geometry("540x520")
        self.minsize(480, 480)
        self.transient(master)

        pad = {"padx": 18, "anchor": "w"}
        ctk.CTkLabel(self, text=tr("Названия через запятую (можно русские и английские)")).pack(pady=(16, 2), **pad)
        self.names = ctk.CTkEntry(self, width=460, placeholder_text=tr("например: ютуб, yt"))
        self.names.pack(**pad)
        ctk.CTkLabel(self, text=tr("Описание (необязательно, видно в «помощь»)")).pack(pady=(12, 2), **pad)
        self.description = ctk.CTkEntry(self, width=460)
        self.description.pack(**pad)

        ctk.CTkLabel(self, text=tr("Что делает")).pack(pady=(12, 2), **pad)
        self.kind = ctk.CTkSegmentedButton(self, values=list(uc.ACTIONS.values()), command=self.kind_changed)
        self.kind.pack(**pad)
        self.hint = ctk.CTkLabel(self, text="", text_color=DIM, wraplength=460, justify="left")
        self.hint.pack(pady=(6, 2), **pad)
        self.target = ctk.CTkTextbox(self, width=460, height=100)
        self.target.pack(**pad)

        self.pick_row = ctk.CTkFrame(self, fg_color="transparent")
        self.pick_row.pack(pady=(6, 0), **pad)
        ctk.CTkButton(self.pick_row, text=tr("Выбрать файл…"), width=130, command=self.pick_file).pack(side="left")
        ctk.CTkButton(self.pick_row, text=tr("Выбрать папку…"), width=130, command=self.pick_folder).pack(side="left", padx=8)

        self.error = ctk.CTkLabel(self, text="", text_color=ERROR, wraplength=460, justify="left")
        self.error.pack(pady=(8, 0), **pad)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", pady=14, padx=18, anchor="e")
        ctk.CTkButton(buttons, text=tr("Отмена"), width=100, fg_color="transparent", border_width=1,
                      text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER,
                      command=self.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text=tr("Сохранить"), width=120, command=self.save).pack(side="left")

        self.names.insert(0, ", ".join(entry["names"]))
        self.description.insert(0, entry.get("description", ""))
        self.kind.set(uc.ACTIONS[entry["action"]])
        self.target.insert("1.0", entry["target"])
        self.kind_changed(self.kind.get())
        self.after(150, self.start)

    def start(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.names.focus_set()

    def action(self):
        return next(key for key, label in uc.ACTIONS.items() if label == self.kind.get())

    def kind_changed(self, _label):
        action = self.action()
        self.hint.configure(text=HINTS[action])
        if action == "shell":
            self.pick_row.pack_forget()
        elif not self.pick_row.winfo_ismapped():
            self.pick_row.pack(pady=(6, 0), padx=18, anchor="w", after=self.target)

    def add_path(self, path):
        text = self.target.get("1.0", "end").strip()
        if self.action() == "set" and text:
            self.target.insert("end", "\n" + path)  # в наборе каждая запись с новой строки
        else:
            self.target.delete("1.0", "end")
            self.target.insert("1.0", path)

    def pick_file(self):
        path = filedialog.askopenfilename(parent=self, title=tr("Выбери программу или файл"))
        if path:
            self.add_path(path.replace("/", "\\"))

    def pick_folder(self):
        path = filedialog.askdirectory(parent=self, title=tr("Выбери папку"))
        if path:
            self.add_path(path.replace("/", "\\"))

    def save(self):
        entry = {
            "names": uc.parse_names(self.names.get()),
            "description": self.description.get().strip(),
            "action": self.action(),
            "target": self.target.get("1.0", "end").strip(),
        }
        problem = uc.validate(entry, self.other_names, self.app.registry.builtin_names)
        if problem:
            self.error.configure(text=problem)
            return
        entries = uc.load()
        if self.index is None:
            entries.append(entry)
        else:
            entries[self.index] = entry
        uc.save(entries)
        self.destroy()
        self.on_saved()