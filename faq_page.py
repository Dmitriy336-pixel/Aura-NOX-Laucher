"""Раздел FAQ в настройках: вопросы раскрываются по клику, сверху поиск по вопросам и ответам.
Сами вопросы лежат в faq_data.py."""
import customtkinter as ctk

import sounds
import theme
from faq_data import FAQ
from i18n import tr

DIM = theme.DIM
ACCENT = theme.ACCENT


class FaqPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.opened = set()  # номера раскрытых вопросов
        self.query = ctk.StringVar()
        self.query.trace_add("write", lambda *_: self.render())
        ctk.CTkEntry(self, textvariable=self.query, placeholder_text=tr("Поиск по вопросам")).pack(
            fill="x", padx=8, pady=(0, 8))
        self.box = ctk.CTkFrame(self, fg_color="transparent")
        self.box.pack(fill="x")
        self.render()

    def matches(self, question, answer, query):
        return not query or query in question.lower() or query in answer.lower()

    def toggle(self, index):
        sounds.play("faq_toggle")
        self.opened.symmetric_difference_update({index})
        self.render()

    def render(self):
        for child in self.box.winfo_children():
            child.destroy()
        query = self.query.get().strip().lower()
        shown = 0
        for index, (question, answer) in enumerate(FAQ):
            if not self.matches(question, answer, query):
                continue
            shown += 1
            expanded = bool(query) or index in self.opened  # при поиске ответы сразу видны
            ctk.CTkButton(
                self.box, text=("▾  " if expanded else "▸  ") + question, anchor="w", height=34,
                fg_color="transparent", hover_color=theme.GHOST_HOVER, text_color=theme.GHOST_TEXT,
                font=ctk.CTkFont(size=14, weight="bold"), command=lambda i=index: self.toggle(i),
            ).pack(fill="x", padx=4, pady=(4, 0))
            if expanded:
                ctk.CTkLabel(
                    self.box, text=answer, text_color=DIM, anchor="w", justify="left", wraplength=470,
                ).pack(fill="x", padx=(34, 12), pady=(0, 6))
        if not shown:
            ctk.CTkLabel(self.box, text=tr("Ничего не найдено"), text_color=DIM).pack(pady=14)
