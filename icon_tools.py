"""Автоматические иконки плиток. Порядок такой:
1. папка готовых иконок icon_pack рядом с программой (файл с именем программы: obs.png подойдёт к obs64.exe);
2. иконка из самой программы (.exe хранит её внутри; для ярлыков и .bat берётся иконка Windows).
Найденная иконка копируется в папку icons, как и выбранная вручную, поэтому дальше всё работает одинаково.
Любая неудача означает просто «иконки нет»: добавление плитки из-за этого никогда не ломается."""
import ctypes
import os
import re
import sys
import uuid
import subprocess
from ctypes import wintypes

from PIL import Image

import tile_icons
from config import BASE_DIR, ICONS_DIR

ICON_PACK_DIR = os.path.join(BASE_DIR, "icon_pack")  # сюда кладут готовые иконки популярных программ
PACK_EXTS = (".png", ".ico", ".webp", ".jpg", ".jpeg", ".bmp")
IS_WINDOWS = sys.platform == "win32"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------- папка готовых иконок
def simplify(name):
    """Имя для сравнения: без регистра, пробелов, дефисов и подчёркиваний."""
    return re.sub(r"[\s_\-]+", "", name.lower())


def pack_index():
    """{упрощённое имя файла: путь} для всех картинок в icon_pack."""
    index = {}
    try:
        entries = sorted(os.listdir(ICON_PACK_DIR))
    except OSError:
        return index
    for fname in entries:
        stem, ext = os.path.splitext(fname)
        if ext.lower() in PACK_EXTS:
            index.setdefault(simplify(stem), os.path.join(ICON_PACK_DIR, fname))
    return index


def candidates(tile):
    """Под какими именами искать иконку: имя файла программы, затем название плитки;
    каждое ещё и без цифр на конце (obs64 -> obs, «chrome 2» -> chrome)."""
    target_stem = os.path.splitext(os.path.basename(tile.get("target") or ""))[0]
    names = []
    for raw in (target_stem, tile.get("name") or ""):
        s = simplify(raw)
        if s:
            names += [s, re.sub(r"[\d.]+$", "", s)]
    unique = []
    for n in names:
        if n and n not in unique:
            unique.append(n)
    return unique


def pack_icon_for(tile):
    index = pack_index()
    for name in candidates(tile):
        if name in index:
            return index[name]
    return None


# ---------------------------------------------------------------- иконка из программы (Windows)
if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    shell32 = ctypes.WinDLL("shell32")

    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    class BITMAP(ctypes.Structure):
        _fields_ = [("bmType", wintypes.LONG), ("bmWidth", wintypes.LONG), ("bmHeight", wintypes.LONG),
                    ("bmWidthBytes", wintypes.LONG), ("bmPlanes", wintypes.WORD),
                    ("bmBitsPixel", wintypes.WORD), ("bmBits", wintypes.LPVOID)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [("hIcon", wintypes.HICON), ("iIcon", ctypes.c_int), ("dwAttributes", wintypes.DWORD),
                    ("szDisplayName", wintypes.WCHAR * 260), ("szTypeName", wintypes.WCHAR * 80)]

    # Типы аргументов обязательны: без них 64-битные дескрипторы обрезаются до 32 бит
    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
    user32.GetIconInfo.restype = wintypes.BOOL
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrivateExtractIconsW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.UINT), wintypes.UINT, wintypes.UINT]
    user32.PrivateExtractIconsW.restype = wintypes.UINT
    gdi32.GetObjectW.argtypes = [wintypes.HGDIOBJ, ctypes.c_int, wintypes.LPVOID]
    gdi32.GetObjectW.restype = ctypes.c_int
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                wintypes.LPVOID, ctypes.POINTER(BITMAPINFO), wintypes.UINT]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    shell32.SHGetFileInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFOW),
                                       wintypes.UINT, wintypes.UINT]
    shell32.SHGetFileInfoW.restype = ctypes.c_void_p

    def _pixels(hdc, bitmap, width, height):
        """Пиксели битовой карты в виде BGRA, строки сверху вниз; None при неудаче."""
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # минус: строки идут сверху вниз
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0   # BI_RGB
        buf = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(hdc, bitmap, 0, height, buf, ctypes.byref(info), 0):
            return None
        return buf.raw

    def _hicon_to_image(hicon):
        """Иконка Windows (дескриптор) -> картинка PIL с прозрачностью."""
        info = ICONINFO()
        if not hicon or not user32.GetIconInfo(hicon, ctypes.byref(info)):
            return None
        hdc = user32.GetDC(None)
        try:
            if not info.hbmColor:      # старые чёрно-белые иконки без цветной карты не поддерживаем
                return None
            bm = BITMAP()
            if not gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
                return None
            width, height = bm.bmWidth, bm.bmHeight
            color = _pixels(hdc, info.hbmColor, width, height)
            if color is None:
                return None
            image = Image.frombytes("RGBA", (width, height), color, "raw", "BGRA")
            if image.getchannel("A").getextrema() == (0, 0):
                # у иконки нет альфа-канала: прозрачность берём из маски (белое в маске = прозрачно)
                mask = _pixels(hdc, info.hbmMask, width, height) if info.hbmMask else None
                if mask is None:
                    image.putalpha(255)
                else:
                    gray = Image.frombytes("RGBA", (width, height), mask, "raw", "BGRA").convert("L")
                    image.putalpha(gray.point(lambda v: 0 if v > 127 else 255))
            return image
        finally:
            user32.ReleaseDC(None, hdc)
            if info.hbmColor:
                gdi32.DeleteObject(info.hbmColor)
            if info.hbmMask:
                gdi32.DeleteObject(info.hbmMask)

    def _from_exe(path, size=256, index=0):
        """Иконка нужного размера из .exe или .dll (берётся ближайшая, Windows при необходимости масштабирует)."""
        icons = (wintypes.HICON * 1)()
        ids = (wintypes.UINT * 1)()
        count = user32.PrivateExtractIconsW(path, index, size, size, icons, ids, 1, 0)
        if count in (0, 0xFFFFFFFF) or not icons[0]:
            return None
        try:
            return _hicon_to_image(icons[0])
        finally:
            user32.DestroyIcon(icons[0])

    def _from_shell(path):
        """Иконка, которую Windows показывает для файла (ярлыки, .bat и прочее), 32 px."""
        info = SHFILEINFOW()
        if not shell32.SHGetFileInfoW(path, 0, ctypes.byref(info), ctypes.sizeof(info), 0x100):  # SHGFI_ICON
            return None
        try:
            return _hicon_to_image(info.hIcon)
        finally:
            if info.hIcon:
                user32.DestroyIcon(info.hIcon)
                
    def _lnk_info(path):
        """Из ярлыка .lnk: (файл со значком, номер значка, программа, на которую он ведёт). Пусто, если не вышло."""
        script = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
                  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ICON_LNK);"
                  "$s.IconLocation;$s.TargetPath")
        try:
            done = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, env=dict(os.environ, ICON_LNK=path), timeout=8, creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return "", 0, ""
        lines = [ln.strip() for ln in done.stdout.decode("utf-8-sig", errors="replace").splitlines()]
        location, target = (lines + ["", ""])[:2]
        icon_path, index = location, 0
        if "," in location:
            head, _, number = location.rpartition(",")
            try:
                icon_path, index = head, int(number)
            except ValueError:
                pass
        return os.path.expandvars(icon_path.strip().strip('"')), index, target

    def _from_lnk(path):
        """Полноразмерная иконка ярлыка: из указанного в нём файла, иначе из программы, на которую он ведёт."""
        icon_path, index, target = _lnk_info(path)
        for source in (icon_path, target):
            if not source or not os.path.isfile(source):
                continue
            ext = os.path.splitext(source)[1].lower()
            try:
                if ext == ".ico":
                    with Image.open(source) as im:
                        return im.convert("RGBA")
                if ext in (".exe", ".dll"):
                    image = _from_exe(source, 256, index if source == icon_path else 0)
                    if image is not None:
                        return image
            except Exception:  # noqa: BLE001  не вышло с этим источником: пробуем следующий
                continue
        return None


def extract_icon(path):
    """Иконка программы как картинка PIL (RGBA) или None. Не бросает исключений."""
    if not IS_WINDOWS or not path or not os.path.exists(path):
        return None
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".ico":
            with Image.open(path) as im:
                return im.convert("RGBA")
        if ext in (".exe", ".dll"):
            image = _from_exe(path)
            if image is not None:
                return image
        if ext == ".lnk":
            image = _from_lnk(path)
            if image is not None:
                return image
        return _from_shell(path)
    except Exception:  # noqa: BLE001  системные вызовы не должны ломать добавление плитки, что бы ни случилось
        return None


# ---------------------------------------------------------------- итог: иконка для плитки
def save_png(image):
    os.makedirs(ICONS_DIR, exist_ok=True)
    name = uuid.uuid4().hex[:10] + ".png"
    image.save(os.path.join(ICONS_DIR, name), "PNG")
    return name


def auto_icon(tile):
    """Подбирает иконку плитке и кладёт её в папку icons. Возвращает имя файла или None."""
    path = pack_icon_for(tile)
    if path:
        try:
            return tile_icons.import_icon(path)
        except OSError:
            pass  # готовая картинка битая: пробуем иконку программы
    image = extract_icon(tile.get("target"))
    if image is not None:
        try:
            return save_png(image)
        except OSError:
            return None
    return None
