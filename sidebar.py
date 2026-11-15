"""Правая узкая панель. Кнопки управляются мышью и клавиатурой (Tab, стрелки, Enter)."""
import customtkinter as ctk

import sounds
import textures
import theme
from tooltip import Tooltip
from i18n import tr

MIN_WIDTH = 64  # кнопка 44 px + по 10 px отступа с каждой стороны
LOCK_ON_TEXT = tr("Плитки закреплены: перетаскивание выключено.\nНажми, чтобы включить")
LOCK_OFF_TEXT = tr("Плитки можно перетаскивать, чтобы менять местами.\nНажми, чтобы закрепить")


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_settings, on_command, on_perf, on_notes, on_lock, width):
        super().__init__(master, width=max(width, MIN_WIDTH), corner_radius=0)
        self.grid_propagate(False)             # держим ширину панели, а не подгоняем под кнопки
        self.grid_rowconfigure(0, weight=1)  # пустое место сверху, оно и прижимает кнопки вниз

        self.command_btn = ctk.CTkButton(
            self, text=">_", width=44, height=44,
            font=ctk.CTkFont(size=16, weight="bold"), command=on_command,
        )
        self.command_btn.grid(row=1, column=0, padx=10, pady=(10, 0))

        # Кнопка заметок
        self.notes_btn = ctk.CTkButton(
            self, text="✎", width=44, height=44,
            font=ctk.CTkFont(size=22), command=on_notes,
        )
        self.notes_btn.grid(row=2, column=0, padx=10, pady=(10, 0))

        # Кнопка блокировки перетаскивания плиток (зелёная = плитки закреплены)
        self.lock_btn = ctk.CTkButton(
            self, text="⇅", width=44, height=44,
            font=ctk.CTkFont(size=22), command=on_lock,
        )
        self.lock_btn.grid(row=3, column=0, padx=10, pady=(10, 0))
        self.lock_tip = Tooltip(self.lock_btn, LOCK_OFF_TEXT, side="left")  # панель справа, поэтому подсказка слева

        # Кнопка режима высокой производительности
        self.perf_btn = ctk.CTkButton(
            self, text="⚡", width=44, height=44,
            font=ctk.CTkFont(size=20), command=on_perf,
        )
        self.perf_btn.grid(row=4, column=0, padx=10, pady=(10, 0))

        self.settings_btn = ctk.CTkButton(
            self, text="⚙", width=44, height=44,
            font=ctk.CTkFont(size=22), command=on_settings,
        )
        self.settings_btn.grid(row=5, column=0, padx=10, pady=10)

        # Кнопки сверху вниз по именам; спрятать можно любую, кроме настроек
        self.named = {
            "command": self.command_btn, "notes": self.notes_btn, "lock": self.lock_btn,
            "perf": self.perf_btn, "settings": self.settings_btn,
        }
        self.visible = {name: True for name in self.named}
        self.glyphs = {name: btn.cget("text") for name, btn in self.named.items()}  # символы кнопок: нужны для текстур
        self.skins = {}   # имя кнопки -> оформление с текстурой (только у тех, кому тема его даёт)
        self.state = {name: {"active": False, "selected": False, "hover": False} for name in self.named}
        # Видимые кнопки по порядку: по ним ходят стрелками вверх и вниз
        self.buttons = list(self.named.values())
        for btn in self.buttons:
            btn.configure(corner_radius=theme.SIDEBAR_RADIUS)  # скругление кнопок панели из темы
            btn.cget("font").configure(family=theme.ICON_FONT)  # значки не зависят от шрифта темы
            btn.bind("<Enter>", lambda e: sounds.play("hover"), add="+")
        self.apply_textures()

    def apply_textures(self):
        """Оформление кнопок из выбранной темы. Если в теме есть texture_button.png, кнопка целиком становится картинкой
        (значок рисуется на ней). Иначе, если есть sidebar_<имя>.png, значок-картинка лежит на цветной кнопке.
        Ничего нет: остаётся цветная кнопка со значком-символом."""
        for name, btn in self.named.items():
            skin = textures.skin(name, self.glyphs[name])
            if skin is not None:
                self.skins[name] = skin
                btn.configure(text="", fg_color="transparent", hover=False, border_width=0)
                btn.bind("<Enter>", lambda e, n=name: self.set_state(n, hover=True))
                btn.bind("<Leave>", lambda e, n=name: self.set_state(n, hover=False))
                self.draw(name)
                continue
            image = theme.image("sidebar_" + name, 30)
            if image is not None:
                btn.configure(image=image, text="")
                # CustomTkinter рисует картинку на уже созданной кнопке только при её перерисовке:
                # без этого значок появляется лишь после первого наведения или нажатия
                btn.configure(fg_color=btn.cget("fg_color"))

    def name_of(self, button):
        return next((name for name, btn in self.named.items() if btn is button), None)

    def set_state(self, name, **changes):
        """Меняет состояние кнопки (включена, выбрана, под курсором) и перерисовывает её, если у неё текстура."""
        state = self.state[name]
        if all(state[key] == value for key, value in changes.items()):
            return
        state.update(changes)
        if name in self.skins:
            self.draw(name)

    def draw(self, name):
        """Картинка кнопки с текстурой по её состоянию: включена важнее наведения."""
        state = self.state[name]
        kind = "active" if state["active"] else ("hover" if state["hover"] else "normal")
        btn = self.named[name]
        btn.configure(image=self.skins[name].image(kind, state["selected"]))
        btn.configure(fg_color="transparent")  # перерисовка: иначе новая картинка не появится до следующего события

    def set_button_visible(self, name, visible):
        """Показать или спрятать кнопку панели: "command", "notes", "lock" или "perf"."""
        self.visible[name] = visible
        if visible:
            self.named[name].grid()      # grid() без аргументов возвращает кнопку на её прежнее место
        else:
            self.named[name].grid_remove()
        self.buttons = [btn for key, btn in self.named.items() if self.visible[key]]

    def set_command_visible(self, visible):
        """Кнопка командной строки есть, только пока строка включена."""
        self.set_button_visible("command", visible)

    def set_button_active(self, button, is_active):
        """Подсветка кнопки, пока её функция включена (цвет «active» темы или текстура включённого состояния)."""
        name = self.name_of(button)
        if name in self.skins:
            self.set_state(name, active=is_active)
        elif is_active:
            button.configure(fg_color=theme.ACTIVE, hover_color=theme.ACTIVE_HOVER)
        else:
            button.configure(fg_color=theme.BUTTON, hover_color=theme.BUTTON_HOVER)

    def set_perf_active(self, is_active):
        """Подсветка кнопки производительности."""
        self.set_button_active(self.perf_btn, is_active)

    def set_lock_active(self, locked):
        """Подсветка кнопки блокировки и текст её подсказки."""
        self.set_button_active(self.lock_btn, locked)
        self.lock_tip.text = LOCK_ON_TEXT if locked else LOCK_OFF_TEXT

    def select(self, index):
        """Подсвечивает кнопку номер index белой рамкой; None снимает подсветку."""
        if index is not None:
            index = min(index, len(self.buttons) - 1)  # кнопок могло стать меньше
        for i, btn in enumerate(self.buttons):
            name = self.name_of(btn)
            if name in self.skins:
                self.set_state(name, selected=(i == index))  # у кнопки с текстурой рамка нарисована в самой картинке
            elif i == index:
                light = ctk.get_appearance_mode() == "Light"
                btn.configure(border_width=4 if light else 3, border_color=theme.SELECT_BORDER)  # на светлой теме толще
            else:
                btn.configure(border_width=0)

    def press(self, index):
        self.buttons[min(index, len(self.buttons) - 1)].invoke()