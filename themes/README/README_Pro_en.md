THEMES (ADVANCED VERSION)

A theme is a folder inside "themes". To select a theme: Settings -> Themes -> click on the card -> "Restart and Apply".
The "themes" folder is located next to main.py (when running from VS Code) or next to the exe (in the compiled version).

HOW TO CREATE YOUR OWN THEME
  Method 1: Settings -> Themes -> "Create custom". A folder with a ready-made theme.json containing all keys will appear.
  Method 2: Copy the _template folder, name it whatever you like (name without _ and dot at the beginning).
  Then open theme.json and modify as needed. Extra keys can be deleted: missing keys will fall back to defaults.
  Add your own icon.png (card image). Without it, the card will display a mockup rendered using the theme's colors.
  Settings -> Themes -> "Refresh list". A theme outside of themes can be added via the "＋ Add theme" button (it will be copied).
  Folders starting with _ or a dot are ignored by the list (this is how the template is hidden).

THEME.JSON FORMAT
  { "name": "Name in list", "colors": {...}, "shapes": {...}, "fonts": {...}, "tiles": {"palette": [...]} }
  A color is a pair [light, dark] in the format "#rrggbb". A single string "#rrggbb" means the same color for both themes.
  Invalid values are skipped and defaults are used.

COLORS (colors)
  button             regular button (also sliders, switches, option selectors)
  button_hover       button under cursor
  button_text        text on a regular button
  button_border      border for bordered buttons
  active             enabled feature: highlighted right panel button
  active_hover       enabled button under cursor
  select_border      border of the selected right panel button
  ghost_text         text on transparent buttons (section list, "Reset", "Cancel")
  ghost_hover        transparent button under cursor
  danger             "Delete" and "Reset all" buttons
  danger_hover       "Delete" button under cursor
  window_bg          window background
  panel_bg           panels and frames background
  panel_top_bg       background for panels inside panels
  card_bg            list rows and theme cards
  card_hover         row or card under cursor
  nav_selected       selected section in the left settings list
  select_bg          selected row: note in the list, command line suggestion
  help_badge         "?" circle badge with tooltip
  help_text          sign inside the "?" circle
  text               regular text
  text_dim           muted text: descriptions, captions, hints
  accent             highlighted text: command names, shortcuts in lists
  error              error messages
  entry_bg           input fields background
  entry_border       input fields border
  entry_text         input fields text
  entry_placeholder  gray hint in an empty field
  textbox_bg         large text area background (notes editor)
  textbox_border     large text area border
  textbox_text       note text
  scrollbar          scrollbar thumb
  scrollbar_hover    scrollbar thumb under cursor
  switch_off         disabled switch
  switch_knob        switch toggle knob
  slider_track       slider track
  dropdown_bg        dropdown list: background
  dropdown_hover     dropdown list: row under cursor
  dropdown_text      dropdown list: text
  segmented_bg       multi-button switch: background and unselected items
  segmented_hover    unselected button under cursor
  cmd_panel_bg       command line: suggestions panel
  cmd_box_bg         command line: window background
  cmd_line           command line: border and separators
  tile_border        "＋" tile border
  tile_select        selected tile border
  tile_text_light    text on dark tiles
  tile_text_dark     text on light tiles
  caption            caption under tile
  drag_source        border of the tile being dragged
  drag_target        border of the tile where the dragged one will land
  tooltip_bg         tooltip: background
  tooltip_text       tooltip: text

SHAPES (shapes), number from 0 to 40
  button_radius      button corner rounding
  frame_radius       panel corner rounding
  entry_radius       input and text fields corner rounding
  tile_radius        tile corner rounding
  sidebar_radius     right panel button corner rounding
  texture_inset      right panel button texture inset from edge, px (if image edges get clipped, set to 2)

FONTS (fonts)
  family             font name, e.g. Segoe UI
  size               main text size, 8..24
  icon_family        right panel button icon font (default Segoe UI Symbol)

TILES PALETTE (tiles.palette)
  List of #rrggbb colors (up to 24): new tiles cycle through them, also used in the tile color picker dialog.

IMAGES (png or webp, preferably square, 128x128+, with transparency)
  icon.png               theme card image in settings (256x256)
  plus.png               icon on the "＋" tile
  sidebar_command.png    command line button
  sidebar_notes.png      notes button
  sidebar_lock.png       tiles lock button
  sidebar_perf.png       performance mode button
  sidebar_settings.png   settings button
  You can provide separate images for light and dark themes: plus_light.png and plus_dark.png.
  Right panel button textures (image instead of color fill, icon is rendered on top):
  texture_button.png         regular button (without this file, no textures are used, buttons remain colored)
  texture_button_hover.png   button under cursor (no file: same texture, slightly lighter)
  texture_active.png         enabled feature (no file: same texture, tinted with active color)
  The icon is loaded from sidebar_<name>.png, or if missing, rendered as a button symbol using icon_family.
  The image is cropped to a square and rounded using sidebar_radius. If texture edges are clipped,
  set shapes.texture_inset = 2.
  If no image is provided, a standard icon is used.