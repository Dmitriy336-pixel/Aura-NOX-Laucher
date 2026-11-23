# Aura NOX Launcher

[Русский](README.ru.md) · [Українська](README.uk.md)

A Windows launcher written in Python and PySide6 (Qt): a window of program tiles, a sidebar with quick buttons, a command bar, notes, visual themes and event sounds. It works with keyboard and mouse, can live in the background and be summoned with a hotkey.

## Features

- **Tiles.** Any program, shortcut or `.bat` file becomes a tile. Tiles can be rearranged with the mouse or keyboard, recolored and given custom icons. Icons are picked automatically from the `icon_pack` folder, from the program itself or from a shortcut.
- **Tile hotkeys.** Every tile has its own key (digits and letters, on any keyboard layout). Pressing it launches the tile at once.
- **Sidebar.** Buttons for settings, the command bar, notes, drag lock and high-performance mode. Unneeded buttons can be hidden.
- **Command bar.** Opens from any program with a global hotkey. It has built-in commands and your own, folder and file navigation, favorite folders, quick notes and a command history (see below). While the bar is open, the screen behind it is blurred and dimmed (configurable, can be turned off).
- **Program search.** The tile with a magnifier (or the “+” itself, depending on a setting) finds a program by name among Start menu and desktop shortcuts and programs registered in Windows; if nothing is found, you can search the disk or pick a file by hand.
- **Three languages.** Russian, English, Ukrainian. The language is chosen on first launch and can be changed in the settings.
- **Notes.** Plain `.md` files in a separate folder, with tabs, live Markdown styling, a formatting toolbar, search by title and text, pinning and autosave.
- **Settings search.** The search field in the settings window finds the item you need and scrolls to it.
- **Themes.** Colors, corner radii, fonts, images and button textures, light and dark mode.
- **Sounds.** A sound for each event, a global volume and an on/off switch.
- **Background mode.** The launcher hides completely and returns on a hotkey. Optional autostart with Windows.
- **Built-in help.** A first-launch screen with the terms and a short guide, plus "FAQ" and "About" tabs in the settings.
- **Single instance.** Starting it again shows the running window instead of opening a second one.

## Requirements

- Windows 10 or 11 (the program uses WinAPI calls).
- Python 3.13 (the version it has been run on).
- Packages: `PySide6`, `Pillow`.

```
pip install PySide6 pillow
```

## Running

```
python main.py
```

The `--background` flag starts the launcher hidden (autostart uses it).

## Controls

### Main window

| Keys | Action |
|---|---|
| Arrow keys | select a tile; on the sidebar, up and down pick a button, left returns to the tiles |
| Tab | move the selection between the tiles and the sidebar |
| Enter | launch the tile, add a program on “+” (or open the search on the magnifier) or press the sidebar button |
| Tile key | launch the tile immediately |
| Delete | menu of the selected tile (delete, color, icon) |
| Right click | the same menu for the tile under the cursor |
| Ctrl + arrow keys | move the selected tile |
| Mouse | hold a tile and drag it to swap places |
| F2 | settings |
| Ctrl+Q | quit the launcher completely |

Dragging can be locked with the ⇅ button on the sidebar.

### Global hotkeys

They work from any program. All three can be changed in the settings.

| Default | Action |
|---|---|
| Ctrl+Alt+Space | show or hide the launcher (background mode) |
| Ctrl+Alt+T | command bar |
| Ctrl+Alt+N | notes |

### Command bar

Tab inserts the selected suggestion, up and down arrows choose a suggestion, Enter runs the command, PgUp and PgDn page through long answers and suggestion pages, Esc closes the bar. With an empty field the up arrow recalls earlier commands (the last 50, kept between launches) and the down arrow goes back to newer ones. The `help` command lists all commands. Background blur is configured in Settings, Appearance, Additional settings, Background blur (strength, dimming, fade-in; in the light theme the background is lightened instead); a click on the blurred background closes the bar. In the English and Ukrainian interface commands are shown by their English names; the Russian names work in every language.

Built-in commands (each has Russian and English names; the table shows both):

| Command | What it does |
|---|---|
| `помощь` / `help` | list of commands |
| `настройки` / `settings`, `скрыть` / `hide`, `выход` / `exit` | control the launcher itself |
| `рб` / `desk` | virtual desktops: `рб 2` switch, `рб +` new, `рб -` close |
| `окно` / `win` | switch to an open window |
| `громкость` / `vol` | system volume: `+`, `-`, `выкл` (mute) |
| `блок` / `lock` | lock the computer |
| `выключить` / `shutdown`, `перезагрузить` / `restart`, `отмена` / `cancel` | shutdown and restart with a delay so you can change your mind |
| `производительность` / `perf` | high-performance mode |
| `заметки` / `notes` | open the notes |
| `папка` / `folder` | folders and files: `folder downloads\...`, a space after the path shows actions (see below) |
| `избранное` / `favs` | favorite folders: `favs`, `favs remove name` |
| `запуск` / `run` | launch a tile by name: `run obs` |
| `записать` / `jot` | quick note: `jot buy bread` |
| `поиск` / `search` | web search: `поиск погода` |
| `скрин` / `screenshot` | screenshot (snipping, Win+Shift+S) |
| `счёт` / `calc` | calculator: `счёт 2+2*3` |
| `условия` / `terms` | terms of use |

**Your own commands** are added in Settings, under "Команды" (Commands), and stored in `commands.json`. There are three kinds of action:

- **open**: open a program, file, folder or website;
- **set**: open several items one after another (one per line);
- **shell**: run a Windows command-line command.

You can put `{}` in the target: the text typed after the command is inserted there. This gives quick searches, for example `https://www.youtube.com/results?search_query={}` for a command `kk something`.

### Folders and files (the `folder` command)

Type `folder downloads\` and the suggestions show what is inside: Tab steps into the selected folder, `..\` goes one level up, PgUp and PgDn page through the suggestions. A path starts with a ready-made name (`downloads`, `documents`, `desktop`, `pictures`, `videos`, `music`, `startup`, `home`), a drive (`c:`) or a name from your favorites. Enter opens a folder in Explorer and runs a file.

A space after a complete path shows the actions available for it:

| Action | What it does |
|---|---|
| `open` | open in Explorer (run a file) |
| `term` | a terminal in this folder |
| `code` | open in VS Code |
| `path` | copy the path to the clipboard |
| `show` | show in Explorer |
| `ls` | what is inside |
| `find text` | find by name inside, with subfolders |
| `new name` | create a subfolder |
| `tile` | add as a tile on the main screen |
| `pin` or `pin name` | add to favorites |

The actions also have Russian names (`открыть`, `терминал`, `код`, `путь`, `показать`, `список`, `найти`, `создать`, `плитка`, `закрепить`). Favorite folders are stored in `favorites.json`, and the `favs` command lists them.

## Language

Languages: Russian, English, Ukrainian. The choice appears on first launch and can be changed later in Settings, General, Language. After a change the launcher offers to restart, because the texts are built at startup. Language names: "Русский", "English", "Українська"; in the English and Ukrainian interface Russian is labelled simply "Ru".

A string with no translation is shown in Russian, so nothing breaks.

## First launch, terms, help

- **First launch.** A three-step window: language, terms of use, a short guide. It appears once and again only if the terms version changes (the `terms_seen` field in `settings.json`).
- **Terms.** The program is free: selling it or asking for donations for it is not allowed; modifying and sharing it for free is. The author answers only for the official version from the official source, not for other people's modified copies or code added to them. The text is always available with the `terms` command and on the "About" tab.
- **FAQ.** A settings tab with answers to common questions.
- **About.** Version, author and official source, the terms, data folders (with an "Open" button), the list of components used, and details for a bug report with one "Copy" button.

## Notes

Each note is a file `<title>.md` in a shared folder, by default `Documents\SharedNotes`. The folder can be changed in Settings, under "Заметки" (Notes). Because of this format, notes can be read and written by other programs too: the window checks the folder every couple of seconds and picks up outside changes. If a file is changed outside while you are editing it, your version is saved separately with a "conflict" mark, so nothing is lost.

- notes open in tabs (the × button closes a tab), and a side panel can show note details: words, characters, lines, modification date;
- the text stays plain Markdown but looks styled: large headings (`#`), **bold**, *italic*, `code`, ~~strikethrough~~, underlined links, quotes; `- [ ]` checkboxes toggle with a click, Enter continues a list, Ctrl+click opens a link;
- a formatting toolbar: headings 1–3, bold (Ctrl+B), italic (Ctrl+I), lists, checkbox, link (Ctrl+K);
- search covers both titles and text;
- pinning: the "★ Закрепить" button or Ctrl+P; pinned notes come first (the list of pinned notes is kept in `.pins.json` inside the notes folder);
- Ctrl+N creates a new note, Ctrl+S saves immediately (otherwise it saves by itself);
- a word and character counter sits at the bottom of the window;
- settings: font size, autosave delay, list order (by date or alphabetical).

## Themes

A theme is a folder `themes/<name>/` with a `theme.json` file and optional images. The full format is described in `themes/README.txt`, which is generated from the tables in `theme.py` and therefore always matches the code.

A theme can change colors (pairs for light and dark mode), corner radii, fonts, the plus image, sidebar button icons (`sidebar_command.png`, `sidebar_notes.png`, `sidebar_lock.png`, `sidebar_perf.png`, `sidebar_settings.png`) and button textures (`texture_button.png`, `texture_button_hover.png`, `texture_active.png`). With textures present, the sidebar buttons become images, for example metallic ones.

Pick a theme in Settings, under "Темы" (Themes): theme cards, an "Add theme" button and creation of a new one. The chosen theme takes effect after a restart (there is a "Restart and apply" button). The dark, light or "as in Windows" mode switches instantly and works with any theme.

## Sounds

Put `.wav` or `.mp3` files into the `sounds` folder next to the program (it is created automatically) and name them after the event. Case does not matter. No file means no sound for that event. Switch and volume: Settings, "Общие" (General), "Звуки" (Sounds).

| File | Plays when |
|---|---|
| `launch` | a tile is launched |
| `error` | an error (a tile did not launch, a command failed) |
| `tile_add` | a tile is added |
| `tile_delete` | a tile is deleted |
| `tile_move` | a tile is moved |
| `select` | the selection frame moves (arrows, Tab) |
| `lock_on` | dragging of tiles is locked |
| `lock_off` | dragging of tiles is unlocked |
| `perf_on` | high-performance mode is on |
| `perf_off` | high-performance mode is off |
| `window_show` | the launcher is shown (hotkey or second start) |
| `window_hide` | the launcher is hidden to the background |
| `settings_open` | settings are opened |
| `settings_close` | settings are closed |
| `command` | the command bar appears |
| `command_ok` | a command succeeded |
| `notes_open` | notes are opened |
| `notes_close` | notes are closed |
| `note_new` | a note is created |
| `note_delete` | a note is deleted |
| `click` | a plain button press; fallback sound for the events below that have no file of their own |
| `nav` | a settings section is switched |
| `toggle_on` | a switch in the settings is turned on |
| `toggle_off` | a switch in the settings is turned off |
| `option` | an option is chosen or a slider is moved in the settings |
| `hotkey_set` | a new hotkey is assigned |
| `menu_open` | the tile menu is opened |
| `drag_start` | a tile is picked up for dragging |
| `hover` | the cursor is over a tile or a sidebar button (no fallback) |
| `note_select` | another note is selected |
| `note_pin` | a note is pinned |
| `note_unpin` | a note is unpinned |
| `cmd_move` | the command bar suggestion changes (arrows); falls back to select |
| `cmd_complete` | a suggestion is inserted (Tab) |
| `command_close` | the command bar is closed with Esc (no fallback) |
| `theme_select` | a theme is chosen |
| `color_set` | a tile color is chosen |
| `faq_toggle` | an FAQ answer is opened or closed |
| `copied` | text is copied (About tab) |
| `note_save` | a note is saved by hand (Ctrl+S) |
| `type` | a key is pressed in the command bar (no fallback) |

A single `click` file brings the whole interface to life: it plays in place of any event that has no file of its own (switches, menus, settings sections, theme choice and so on) and on any button in the settings and notes windows. For variety, add files for individual events. `hover`, `command_close` and `type` have no fallback: they play only if the file exists. `cmd_move` plays `select` by default.

The current list is always available in the folder itself, in the file `sound_names.txt` (`имена_звуков.txt` in Russian, `імена_звуків.txt` in Ukrainian).

Notes on sound:

- Sounds play through the system MCI (`winmm`), so the launcher's volume is adjustable separately from the system volume.
- Each sound is opened in advance and plays as a fresh instance: there is no delay and repeats sound identical.
- Bluetooth headphones go to sleep after a pause and may swallow or distort the start of a short sound. This is a headphone quirk, not a launcher bug. Sounds with a little silence at the start help.

## High-performance mode

The sidebar button (or the `производительность` command) switches the Windows power plan to high performance. The previous plan is remembered and restored when you turn it off.

## Where things are stored

Data lives next to the program (next to the `exe` in the built version) and survives restarts.

| What | Where |
|---|---|
| Tiles | `tiles.json` |
| Settings | `settings.json` |
| Your commands | `commands.json` |
| Favorite folders | `favorites.json` |
| Command history | `history.json` |
| Tile icons | `icons/` |
| Ready-made icons of popular programs | `icon_pack/` (a file named after the program: `obs.png` fits `obs64.exe`) |
| Themes | `themes/` |
| Sounds | `sounds/` |
| Notes | `Documents\SharedNotes` or the folder from the settings |

Data files are written through a temporary file, so closing the program mid-write does not corrupt them. A damaged JSON file is set aside with the `.broken` extension instead of being overwritten.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | entry point, single-instance guard |
| `app.py` | main window: assembles the parts and decides what to do on actions |
| `config.py` | paths, sizes, default settings |
| `storage.py` | loading and saving tiles and settings |
| `tile_grid.py`, `tile_icons.py`, `icon_tools.py` | tile grid, icons |
| `sidebar.py`, `textures.py` | sidebar and its button textures |
| `screen_blur.py` | blurred background behind the command bar |
| `add_program.py`, `programs.py` | the “Add a program” window and the search for installed programs |
| `theme.py`, `theme_page.py` | themes |
| `command_bar.py`, `commands.py`, `builtin_commands.py`, `user_commands.py`, `calc.py` | command bar |
| `path_nav.py` | the `folder` command: folder and file navigation, favorites |
| `notes_window.py`, `notes_store.py`, `notes_settings.py`, `md_edit.py` | notes and the Markdown-styled editor |
| `settings_window.py`, `settings_data.py`, `controls_page.py`, `commands_page.py`, `color_picker.py`, `hotkey_capture.py` | settings window |
| `hotkey.py`, `keyfix.py` | global hotkeys, clipboard shortcuts on any layout |
| `sounds.py` | event sounds |
| `i18n.py`, `lang_en.py`, `lang_uk.py` | languages: the `tr()` function and translation tables |
| `legal.py`, `firstrun.py` | terms of use, first-launch window |
| `about_page.py`, `faq_page.py`, `faq_data.py` | "About" and "FAQ" tabs |
| `ui_kit.py`, `dialogs.py` | shared Qt interface widgets and dialogs |
| `autostart.py`, `powerplan.py`, `winapi.py`, `single_instance.py`, `launchers.py` | Windows integration |

### Adding a language

Russian strings in the code serve as keys: `tr("text")` looks the translation up in the language table and shows the key itself if there is none. To add a language `xx`: create `lang_xx.py` with a dictionary `XX` (see `lang_en.py`), add the language to `LANGS` in `i18n.py`, translate the texts in `legal.py` and `faq_data.py`, and the event names in `sounds.py`.

The settings shown in the window are described in `settings_data.py`; factory values live in `config.DEFAULT_SETTINGS`. A new setting means one line in each place.

## Building an exe

The build uses PyInstaller with `main.spec`:

```
pip install pyinstaller
pyinstaller main.spec
```

The finished program appears in `dist\Aura NOX Launcher\` (a folder build rather than a single exe: antivirus programs complain about it less; Qt makes the folder noticeably larger than it was with CustomTkinter). Data files will live next to `Aura NOX Launcher.exe`, and the `themes`, `sounds` and `icon_pack` folders must be copied there so that themes, sounds and ready-made icons work.

## Official sources

The original program can be downloaded only from these places:

- **GitHub:** https://github.com/Dmitriy336-pixel/Aura-NOX-Laucher
- **Telegram:** [channel link]
- **YouTube:** [channel link]

Anything called "Aura NOX Launcher" that did not come from these places is not from the author. The author is not responsible for such versions or for any code added to them (see the terms of use in the program).

## Credits and licenses

Interface sound effects: **Universal UI Soundpack** by Nathan Gibson ([author's site](https://nathangibson.myportfolio.com)), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). If you modified the sounds (trimmed them, changed the volume), the license requires you to say so.

The program also uses Python, PySide6 / Qt (LGPL v3) and Pillow (HPND). The same is listed on the "About" tab.

## Troubleshooting

- **A hotkey does not work.** Another program already holds that combination. The launcher tells you at startup and turns the feature off; pick another combination in the settings.
- **No sound.** Check the switch and volume in Settings, General, Sounds, and the file name: it must match the event name.
- **A theme did not apply.** A theme takes effect after a restart: press "Restart and apply".
- **The launcher "disappeared".** It is in background mode: summon it with the hotkey or run `main.py` again.
