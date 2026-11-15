"""Окно заметок: слева список, справа редактор.
Файлы лежат в общей папке вне проекта (см. notes_store.py).
Сохраняется само через пару мгновений после последней правки.
Раз в пару секунд окно смотрит в папку: заметки, изменённые другой программой, подхватываются сами."""
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

import sounds
import theme
from config import ICON_PATH
from notes_store import NoteStore
from scrollfix import fix_later
from i18n import tr

SAVE_DELAY = 700    # сколько мс тишины после правки ждём, прежде чем писать на диск
POLL_DELAY = 2000   # как часто смотрим, не менялась ли папка снаружи, мс

SELECT_BG = theme.SELECT_BG   # выбранная заметка в списке
DIM = theme.DIM
ERROR = theme.ERROR
ALT = 0x20000  # бит Alt в event.state (Ctrl+Alt = AltGr на некоторых раскладках)


class NotesWindow(ctk.CTkToplevel):
    def __init__(self, master, store, on_folder_change, anchor=None):
        super().__init__(master)
        self.store = store
        self.on_folder_change = on_folder_change  # on_folder_change(новая папка): запомнить в настройках
        settings = getattr(master, "settings", {})  # размер шрифта, автосохранение и порядок задаются в настройках
        self.save_delay = settings.get("notes_autosave_ms", SAVE_DELAY)
        self.sort = settings.get("notes_sort", "date")
        self.text_font = ctk.CTkFont(size=settings.get("notes_font_size", 14))
        self.current = None        # заголовок открытой заметки (= имя файла без .md)
        self.loaded_text = ""      # текст, который считаем «как на диске»
        self.loaded_mtime = None   # время файла, когда мы его последний раз читали или писали
        self.dirty = False         # есть несохранённые правки
        self.loading = False       # True, пока поля заполняем из кода, а не печатает человек
        self.filter_text = ""
        self.text_cache = {}       # заголовок -> (время файла, текст в нижнем регистре): для поиска по тексту
        self.list_signature = None
        self.save_job = None
        self.poll_job = None

        self.title(tr("Заметки"))
        self.minsize(420, 300)
        self.place_near(anchor, 530, 400)
        if os.path.exists(ICON_PATH):
            self.after(300, self.apply_icon)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- слева: новая заметка, поиск, список, папка ---
        side = ctk.CTkFrame(self, width=190, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(2, weight=1)

        ctk.CTkButton(side, text=tr("＋  Новая заметка"), command=self.new_note).grid(
            row=0, column=0, padx=10, pady=(10, 6), sticky="ew")
        self.search = ctk.CTkEntry(side, placeholder_text=tr("Поиск по названию и тексту"))
        self.search.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
        self.search.bind("<KeyRelease>", self.on_search)

        self.list = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.list.grid(row=2, column=0, padx=4, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)

        self.folder_label = ctk.CTkLabel(
            side, text="", anchor="w", justify="left", wraplength=165,
            text_color=DIM, font=ctk.CTkFont(size=11),
        )
        self.folder_label.grid(row=3, column=0, padx=12, pady=(6, 2), sticky="w")
        ctk.CTkButton(
            side, text=tr("Папка…"), height=26, fg_color="transparent", border_width=1,
            text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER, command=self.choose_folder,
        ).grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew")

        # --- справа: заголовок, текст, строка состояния ---
        editor = ctk.CTkFrame(self, fg_color="transparent")
        editor.grid(row=0, column=1, padx=(8, 10), pady=10, sticky="nsew")
        editor.grid_columnconfigure(0, weight=1)
        editor.grid_rowconfigure(1, weight=1)

        self.title_var = ctk.StringVar()
        self.title_entry = ctk.CTkEntry(
            editor, textvariable=self.title_var, height=38, font=ctk.CTkFont(size=18, weight="bold"))
        self.title_entry.grid(row=0, column=0, sticky="ew")
        self.title_var.trace_add("write", lambda *_: self.on_edit())
        self.title_entry.bind("<FocusOut>", lambda e: self.after(1, self.sync_title))

        self.text = ctk.CTkTextbox(editor, wrap="word", undo=True, font=self.text_font)
        self.text.grid(row=1, column=0, pady=8, sticky="nsew")
        self.text.bind("<<Modified>>", self.on_text_modified)

        bottom = ctk.CTkFrame(editor, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(bottom, text="", anchor="w", text_color=DIM, font=ctk.CTkFont(size=12))
        self.status.grid(row=0, column=0, sticky="w")
        self.counter = ctk.CTkLabel(bottom, text="", text_color=DIM, font=ctk.CTkFont(size=12))
        self.counter.grid(row=0, column=1, padx=(8, 8))
        self.pin_btn = ctk.CTkButton(
            bottom, text=tr("★ Закрепить"), width=110, fg_color="transparent", border_width=1,
            text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER, command=self.toggle_pin,
        )
        self.pin_btn.grid(row=0, column=2, padx=(0, 6))
        self.delete_btn = ctk.CTkButton(
            bottom, text=tr("Удалить"), width=90, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self.delete_note,
        )
        self.delete_btn.grid(row=0, column=3)

        # Горячие клавиши (Ctrl+N, Ctrl+S, Delete для удаления)
        for widget in (self, self.title_entry, self.text):
            widget.bind("<Control-Key>", self.on_ctrl_key)
            widget.bind("<Delete>", self.on_delete_key)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_folder()
        self.open_first()
        self.poll_job = self.after(POLL_DELAY, self.poll)
        self.bring_to_front()

    def apply_icon(self):
        try:
            self.iconbitmap(ICON_PATH)
        except tk.TclError:
            pass

    # --- положение и показ окна ---
    def place_near(self, anchor, width, height):
        scale = self.winfo_fpixels("1i") / 96
        w, h = int(width * scale), int(height * scale)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if anchor:
            x, y = anchor[0] - w - 8, anchor[1] - h // 2
        else:
            x, y = (sw - w) // 2, (sh - h) // 2
        x = max(0, min(x, sw - w - 75))
        y = max(0, min(y, sh - h - 60))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def bring_to_front(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, self.drop_topmost)
        self.focus_force()

    def drop_topmost(self):
        if self.winfo_exists():
            self.attributes("-topmost", False)

    # --- вспомогательное ---
    def set_status(self, text, error=False):
        self.status.configure(text=text, text_color=ERROR if error else DIM)

    def show_folder(self):
        self.folder_label.configure(text=tr('Папка: {folder}', folder=self.store.folder))

    def set_title_quiet(self, title):
        self.loading = True
        self.title_var.set(title)
        self.loading = False

    def set_editable(self, editable):
        state = "normal" if editable else "disabled"
        self.title_entry.configure(state=state)
        self.text.configure(state=state)
        self.delete_btn.configure(state=state)
        self.pin_btn.configure(state=state)

    def update_counter(self):
        """Слова и символы открытой заметки под редактором."""
        if self.current is None:
            self.counter.configure(text="")
            return
        text = self.text.get("1.0", "end-1c")
        self.counter.configure(text=tr('{v} сл. · {v2} симв.', v=len(text.split()), v2=len(text)))

    def fill(self, title, text):
        self.set_editable(True)
        self.loading = True
        self.title_var.set(title)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.loading = False
        self.update_counter()
        self.update_pin_button()

    def clear_editor(self):
        self.fill("", "")
        self.current = None
        self.loaded_text, self.loaded_mtime, self.dirty = "", None, False
        self.update_counter()
        self.update_pin_button()
        self.set_editable(False)
        self.set_status(tr("Нет заметок. Нажми «Новая заметка» (Ctrl+N)"))
        self.refresh_list(force=True)

    def on_ctrl_key(self, event):
        if event.state & ALT:
            return None
        if event.keycode == 78:   # N
            self.new_note()
            return "break"
        if event.keycode == 83:   # S
            sounds.play("note_save")
            self.save_now()
            return "break"
        if event.keycode == 80:   # P
            self.toggle_pin()
            return "break"
        return None

    def on_delete_key(self, event):
        # Delete удаляет заметку, только когда фокус не в поле ввода: в заголовке, тексте и поиске он стирает символ
        if isinstance(self.focus_get(), (tk.Text, tk.Entry)):
            return None
        if self.current:
            self.delete_note()
            return "break"
        return None

    # --- список заметок ---
    def scan(self):
        try:
            return self.store.list_notes(self.sort)  # порядок из настроек: date или name
        except OSError:
            self.set_status(tr("Папка с заметками недоступна"), error=True)
            return None

    def refresh_list(self, force=False):
        notes = self.scan()
        if notes is None:
            return None
        signature = (tuple(notes), self.filter_text, self.current, tuple(self.store.pinned()))
        if force or signature != self.list_signature:
            self.list_signature = signature
            self.build_list(notes)
        return notes

    def build_list(self, notes):
        for child in self.list.winfo_children():
            child.destroy()
        pins = {t.lower() for t in self.store.pinned()}
        shown = [title for title, _mtime in notes if self.matches(title)]
        shown.sort(key=lambda title: title.lower() not in pins)  # закреплённые сверху, порядок внутри групп прежний
        if not shown:
            ctk.CTkLabel(
                self.list, text=tr("Ничего не найдено") if self.filter_text else tr("Пока пусто"),
                text_color=DIM).grid(row=0, column=0, pady=12)
        for row, title in enumerate(shown):
            selected = title == self.current
            ctk.CTkButton(
                self.list, text=("★ " + title) if title.lower() in pins else title, anchor="w", height=32,
                fg_color=SELECT_BG if selected else "transparent",
                hover_color=SELECT_BG, text_color=theme.GHOST_TEXT,
                command=lambda t=title: self.select(t),
            ).grid(row=row, column=0, pady=1, sticky="ew")

    def matches(self, title):
        """Подходит ли заметка под поиск: совпадение в названии или в тексте."""
        query = self.filter_text
        if not query or query in title.lower():
            return True
        mtime = self.store.mtime(title)
        cached = self.text_cache.get(title)
        if cached is None or cached[0] != mtime:
            try:
                cached = (mtime, self.store.read(title)[0].lower())
            except OSError:
                return False
            self.text_cache[title] = cached
        return query in cached[1]

    def toggle_pin(self):
        if self.current is None:
            return
        pin = not self.store.is_pinned(self.current)
        try:
            self.store.set_pinned(self.current, pin)
        except OSError as e:
            self.set_status(tr('Не удалось закрепить: {e}', e=e), error=True)
            return
        sounds.play("note_pin" if pin else "note_unpin")
        self.update_pin_button()
        self.refresh_list(force=True)

    def update_pin_button(self):
        pinned = self.current is not None and self.store.is_pinned(self.current)
        self.pin_btn.configure(text=tr("★ Открепить") if pinned else tr("★ Закрепить"))

    def on_search(self, event=None):
        self.filter_text = self.search.get().strip().lower()
        self.refresh_list(force=True)

    # --- открыть, создать, удалить ---
    def select(self, title):
        if title == self.current:
            return
        if self.save_now():
            sounds.play("note_select")
            self.load(title)

    def load(self, title):
        try:
            text, mtime = self.store.read(title)
        except OSError:
            self.refresh_list(force=True)
            return False
        self.current = title
        self.loaded_text, self.loaded_mtime = text, mtime
        self.dirty = False
        self.fill(title, text)
        self.set_status("")
        self.refresh_list(force=True)
        return True

    def open_first(self):
        notes = self.refresh_list(force=True)
        if notes:
            self.load(notes[0][0])
        elif notes is not None:
            self.clear_editor()

    def new_note(self):
        if not self.save_now():
            return
        title = self.store.unique_title(tr("Новая заметка"))
        try:
            self.store.write(title, "")
        except OSError as e:
            messagebox.showerror(tr("Заметки"), tr('Не удалось создать заметку:\n{e}', e=e), parent=self)
            return
        self.search.delete(0, "end")
        self.filter_text = ""
        sounds.play("note_new")
        if self.load(title):
            self.title_entry.focus_set()
            self.title_entry.select_range(0, "end")

    def delete_note(self):
        if self.current is None:
            return
        if not messagebox.askyesno(
                tr("Удалить заметку"), tr('Удалить «{current}»?\nФайл будет удалён с диска.', current=self.current), parent=self):
            return
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        try:
            self.store.delete(self.current)
        except FileNotFoundError:
            pass
        except OSError as e:
            messagebox.showerror(tr("Заметки"), tr('Не удалось удалить:\n{e}', e=e), parent=self)
            return
        sounds.play("note_delete")
        self.dirty = False
        self.current = None
        self.open_first()

    # --- правка и сохранение ---
    def on_text_modified(self, event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if not self.loading:
            self.on_edit()
        self.update_counter()

    def on_edit(self):
        if self.loading or self.current is None:
            return
        self.dirty = True
        self.set_status(tr("Изменено… (сохранение...)"))
        if self.save_job:
            self.after_cancel(self.save_job)
        self.save_job = self.after(self.save_delay, self.save_now)

    def sync_title(self):
        if self.winfo_exists() and self.save_now() and self.current:
            self.set_title_quiet(self.current)

    def save_now(self):
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        if not self.dirty or self.current is None:
            return True

        store, old = self.store, self.current
        text = self.text.get("1.0", "end-1c")
        wanted = self.title_var.get()
        new = store.unique_title(wanted, own=old) if wanted.strip() else old

        conflict = False
        disk_mtime = store.mtime(old)
        if disk_mtime is not None and disk_mtime != self.loaded_mtime:
            try:
                conflict = store.read(old)[0] != self.loaded_text
            except OSError:
                pass
        try:
            if conflict:
                new = store.unique_title(tr('{new} (конфликт)', new=new))
            elif new != old and disk_mtime is not None:
                store.rename(old, new)
            self.loaded_mtime = store.write(new, text)
        except OSError as e:
            self.set_status(tr('Не удалось сохранить: {e}', e=e), error=True)
            return False

        self.current = new
        self.loaded_text = text
        self.dirty = False
        if conflict:
            self.set_title_quiet(new)
            self.set_status(tr('Файл изменили снаружи: версия сохранена как «{new}»', new=new), error=True)
        else:
            self.set_status(tr('Сохранено {v}', v=time.strftime('%H:%M:%S')))
        self.refresh_list(force=True)
        return True

    # --- слежение за папкой ---
    def poll(self):
        self.poll_job = None
        notes = self.refresh_list()
        if notes is not None and self.current is not None and not self.dirty:
            mtimes = {title.lower(): mtime for title, mtime in notes}
            disk_mtime = mtimes.get(self.current.lower())
            if disk_mtime is None:
                self.open_first()
            elif disk_mtime != self.loaded_mtime:
                self.reload_current()
        self.poll_job = self.after(POLL_DELAY, self.poll)

    def reload_current(self):
        try:
            text, mtime = self.store.read(self.current)
        except OSError:
            return
        if text != self.loaded_text:
            cursor = self.text.index("insert")
            self.fill(self.current, text)
            try:
                self.text.mark_set("insert", cursor)
            except tk.TclError:
                pass
            self.set_status(tr("Обновлено из файла"))
        self.loaded_text, self.loaded_mtime = text, mtime

    # --- папка и закрытие ---
    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self, title=tr("Папка для заметок"), initialdir=self.store.folder)
        if not folder:
            return
        folder = os.path.normpath(folder)
        if os.path.normcase(folder) == os.path.normcase(self.store.folder):
            return
        if not self.save_now():
            return
        try:
            store = NoteStore(folder)
        except OSError as e:
            messagebox.showerror(tr("Заметки"), tr('Не удалось открыть папку:\n{e}', e=e), parent=self)
            return
        self.store = store
        self.text_cache.clear()
        self.on_folder_change(store.folder)
        self.current = None
        self.show_folder()
        self.open_first()
        self.set_status(tr("Папка изменена."))

    def apply_settings(self):
        """Подхватывает настройки заметок, изменённые в окне настроек, без перезапуска."""
        settings = getattr(self.master, "settings", {})
        self.save_delay = settings.get("notes_autosave_ms", SAVE_DELAY)
        self.text_font.configure(size=settings.get("notes_font_size", 14))
        sort = settings.get("notes_sort", "date")
        if sort != self.sort:
            self.sort = sort
            self.refresh_list(force=True)

    def use_folder(self, store):
        """Переключает окно на другую папку заметок (когда её сменили в настройках)."""
        if not self.save_now():
            return
        self.store = store
        self.text_cache.clear()
        self.current = None
        self.show_folder()
        self.open_first()

    def on_close(self):
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        if self.poll_job:
            self.after_cancel(self.poll_job)
            self.poll_job = None

        if not self.save_now() and not messagebox.askyesno(
                tr("Заметки"), tr("Не удалось сохранить последние правки. Закрыть всё равно?"), parent=self):
            return
        sounds.play("notes_close")
        self.destroy()