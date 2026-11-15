"""Схемы электропитания Windows через powercfg (права администратора не нужны)."""
import re
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"          # «Сбалансированная»
HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"  # «Высокая производительность»
ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"          # «Максимальная производительность»
GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")


def _powercfg(*args):
    """Запускает powercfg. Возвращает (успех, текст вывода)."""
    try:
        done = subprocess.run(["powercfg", *args], capture_output=True, creationflags=NO_WINDOW)
    except OSError:
        return False, ""
    return done.returncode == 0, done.stdout.decode("latin-1")  # GUID состоит из латиницы и цифр


def active_scheme():
    """GUID текущей схемы электропитания или None."""
    ok, out = _powercfg("/getactivescheme")
    found = GUID.search(out) if ok else None
    return found.group(0).lower() if found else None


def set_active(guid):
    return _powercfg("/setactive", guid)[0]


def enable_performance(known=None):
    """Включает схему высокой производительности и возвращает её GUID (или None, если не вышло).
    Если такой схемы в системе нет (так бывает на ноутбуках), создаёт копию из шаблона.
    known: GUID схемы, которую мы уже создавали раньше (чтобы не плодить копии)."""
    for guid in (known, HIGH_PERFORMANCE):
        if guid and set_active(guid):
            return guid
    for template in (HIGH_PERFORMANCE, ULTIMATE):
        ok, out = _powercfg("/duplicatescheme", template)
        created = GUID.search(out) if ok else None
        if created and set_active(created.group(0)):
            return created.group(0).lower()
    return None