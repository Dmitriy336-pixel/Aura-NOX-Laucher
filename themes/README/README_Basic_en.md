THEMES (LIGHTWEIGHT VERSION)

A theme is a folder inside "themes". To select a theme: Settings -> Themes -> click on the card -> "Restart and Apply".
The "themes" folder must be located next to main.py (when running from VS Code) or next to the exe (in the compiled version).

HOW TO CREATE YOUR OWN THEME
  1. Copy the _template folder and name it whatever you like (name without _ at the beginning).
  2. Open theme.json and change the name and colors.
  3. Add your icon.png (card image). Without it, the card will display a mockup rendered using the theme's colors.
  4. Settings -> Themes -> "Refresh list". If the theme is located outside of themes, click "＋ Add theme": it will be copied.
  Folders starting with _ or a dot are ignored by the list (this is how the template is hidden).

theme.json
  {
    "name": "Name in list",
    "colors": { "button": ["#light", "#dark"], ... }
  }
  Colors are specified as a pair: the first for the light theme, the second for the dark theme. A single string "#rrggbb" means the same color for both.
  Missing colors fall back to defaults. Invalid colors are skipped.

Colors
  button, button_hover, button_text     regular buttons, their color under cursor, and text color on them
  active, active_hover                  enabled feature: highlighted button on the right panel
  select_border                         border of the selected panel button
  window_bg                             window background          (optional)
  panel_bg, panel_top_bg                panels and nested panels background  (optional)
  text                                  regular text color         (optional)

Images (png or webp, preferably square, 128x128+, with transparency)
  icon.png                              theme card image in settings (256x256)
  plus.png                              icon on the "+" tile
  sidebar_command.png                   command line button
  sidebar_notes.png                     notes button
  sidebar_lock.png                      tiles lock button
  sidebar_perf.png                      performance mode button
  sidebar_settings.png                  settings button
  You can provide separate images for light and dark themes: plus_light.png and plus_dark.png.
  If no image is provided, a standard icon is used.