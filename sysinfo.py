"""Системная информация: батарея, диски, IP, аптайм; Wi-Fi; Bluetooth.
Батарея, диски и аптайм работают и без psutil (через системные вызовы Windows)."""
import base64
import ctypes
import re
import shutil
import socket
import subprocess
import time
from ctypes import wintypes

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ── батарея ───────────────────────────────────────────────────────────────────
class _PowerStatus(ctypes.Structure):
    _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("percent", ctypes.c_ubyte),
                ("saver", ctypes.c_ubyte), ("life", wintypes.DWORD), ("full_life", wintypes.DWORD)]


def battery():
    """(percent, charging, has_battery)."""
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return None, False, False
        return int(b.percent), bool(b.power_plugged), True
    except Exception:
        pass
    try:
        status = _PowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None, False, False
        if status.flag & 128 or status.percent == 255:  # 128: батареи нет, 255: заряд неизвестен
            return None, False, False
        return int(status.percent), status.ac == 1, True
    except Exception:
        return None, False, False


# ── диски ─────────────────────────────────────────────────────────────────────
def disks():
    """[(буква вида 'C:', всего_ГБ, свободно_ГБ), ...]"""
    result = []
    try:
        kernel = ctypes.windll.kernel32
        mask = kernel.GetLogicalDrives()
        for i in range(26):
            if not mask >> i & 1:
                continue
            root = f"{chr(65 + i)}:\\"
            if kernel.GetDriveTypeW(root) not in (2, 3, 4):  # съёмный, жёсткий, сетевой (не CD и не RAM)
                continue
            try:
                usage = shutil.disk_usage(root)
            except OSError:  # пустой картридер, недоступный сетевой диск
                continue
            result.append((root[:2], round(usage.total / 1024 ** 3, 1), round(usage.free / 1024 ** 3, 1)))
        return result
    except (AttributeError, OSError):
        pass
    try:  # не Windows: через psutil
        import psutil
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            result.append((part.mountpoint, round(usage.total / 1024 ** 3, 1), round(usage.free / 1024 ** 3, 1)))
    except Exception:
        pass
    return result


# ── IP ────────────────────────────────────────────────────────────────────────
def local_ip():
    """Локальный IP-адрес."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "не определён"


# ── аптайм ───────────────────────────────────────────────────────────────────
def uptime():
    """Строка вида '2 ч 15 мин' (с днями, если больше суток)."""
    try:
        get_ticks = ctypes.windll.kernel32.GetTickCount64
        get_ticks.restype = ctypes.c_ulonglong
        sec = int(get_ticks() // 1000)
    except Exception:
        try:
            import psutil
            sec = int(time.time() - psutil.boot_time())
        except Exception:
            return "?"
    days, rem = divmod(sec, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if days:
        return f"{days} д {h} ч {m} мин"
    if h:
        return f"{h} ч {m} мин"
    return f"{m} мин"


# ── Wi-Fi ─────────────────────────────────────────────────────────────────────
def _oem_encoding():
    """Кодировка вывода консольных программ (netsh): cp866 на русской Windows, cp852 на польской и т.д."""
    try:
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        return "cp866"


def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding=_oem_encoding(),
                           errors="replace", creationflags=NO_WINDOW, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or "") + (r.stderr or "")


def wifi_status():
    """(имя_сети_или_None, есть_ли_Wi-Fi_адаптер)."""
    out = _run(["netsh", "wlan", "show", "interfaces"])
    state = re.search(r"(?mi)^\s*(?:State|Состояние|Стан)\s*:\s*(.+)$", out)
    ssid = re.search(r"(?mi)^\s*SSID\s*:\s*(.+)$", out)  # строка есть только у подключённого адаптера
    if not state and not ssid:
        return None, False  # адаптера нет или служба WLAN выключена
    return (ssid.group(1).strip() if ssid else None), True


_nets_cache = (0.0, [])


def wifi_networks(max_age=15):
    """Доступные сети [(ssid, сигнал%), ...] от сильной к слабой. Сканирование медленное, поэтому
    результат помнится max_age секунд: подсказки не будут дёргать netsh на каждую букву."""
    global _nets_cache
    if time.time() - _nets_cache[0] < max_age:
        return _nets_cache[1]
    out = _run(["netsh", "wlan", "show", "networks", "mode=Bssid"])
    best = {}
    for block in re.split(r"(?m)^(?=\s*SSID\s+\d+\s*:)", out):
        name = re.match(r"\s*SSID\s+\d+\s*:\s*(.*)", block)
        if not name or not name.group(1).strip():
            continue  # скрытые сети без имени не показываем
        signals = [int(x) for x in re.findall(r"(?:Signal|Сигнал|Сигнал)\s*:\s*(\d+)\s*%", block)]
        ssid = name.group(1).strip()
        best[ssid] = max(best.get(ssid, 0), max(signals) if signals else 0)
    nets = sorted(best.items(), key=lambda item: item[1], reverse=True)[:16]
    _nets_cache = (time.time(), nets)
    return nets


def wifi_connect(ssid):
    """Подключиться к сохранённому профилю. True, если Windows приняла команду."""
    try:
        r = subprocess.run(["netsh", "wlan", "connect", f"name={ssid}"], capture_output=True,
                           creationflags=NO_WINDOW, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def wifi_toggle():
    """Отключиться от Wi-Fi или подключиться к последней сохранённой сети."""
    ssid, enabled = wifi_status()
    if not enabled:
        return False, "Wi-Fi адаптер не найден"
    if ssid:
        _run(["netsh", "wlan", "disconnect"])
        return True, "Wi-Fi отключён"
    out = _run(["netsh", "wlan", "show", "profiles"])
    profiles = re.findall(r":\s*(.+)", out)
    if profiles:
        last = profiles[-1].strip()
        ok = wifi_connect(last)
        return True, f"Подключение к «{last}»..." if ok else f"Не удалось подключиться к «{last}»"
    return True, "Wi-Fi включён, сохранённых сетей нет"


# ── Bluetooth ─────────────────────────────────────────────────────────────────
# Радиомодулями Windows управляет через WinRT (Windows.Devices.Radios): без прав администратора.
# Старый способ (Disable-PnpDevice) требовал админа и брал первое попавшееся устройство из класса Bluetooth.
_BT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($op, $type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
  }
  [void][Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType=WindowsRuntime]
  [void][Windows.Devices.Radios.RadioAccessStatus, Windows.System.Devices, ContentType=WindowsRuntime]
  [void][Windows.Devices.Radios.RadioState, Windows.System.Devices, ContentType=WindowsRuntime]
  $access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
  if ($access -ne 'Allowed') { Write-Output 'BT:denied'; exit }
  $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
  $bt = $radios | Where-Object { $_.Kind -eq 'Bluetooth' } | Select-Object -First 1
  if (-not $bt) { Write-Output 'BT:none'; exit }
  $want = '__WANT__'
  if ($want -eq 'status') { Write-Output ('BT:' + $bt.State.ToString().ToLower()); exit }
  if ($want -eq 'toggle') { if ($bt.State -eq 'On') { $want = 'off' } else { $want = 'on' } }
  if ($want -eq 'on') { $state = [Windows.Devices.Radios.RadioState]::On } else { $state = [Windows.Devices.Radios.RadioState]::Off }
  $res = Await ($bt.SetStateAsync($state)) ([Windows.Devices.Radios.RadioAccessStatus])
  if ($res -eq 'Allowed') { Write-Output ('BT:' + $want) } else { Write-Output 'BT:denied' }
} catch {
  Write-Output ('BT:error ' + $_.Exception.Message)
}
"""


def bluetooth_set(want="toggle"):
    """Bluetooth: want = 'on' | 'off' | 'toggle' | 'status'. Возвращает (ok, сообщение)."""
    if want not in ("on", "off", "toggle", "status"):
        want = "toggle"
    script = _BT_SCRIPT.replace("__WANT__", want)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", encoded],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=NO_WINDOW, timeout=25)
    except FileNotFoundError:
        return False, "PowerShell не найден"
    except subprocess.TimeoutExpired:
        return False, "Bluetooth не ответил за 25 секунд"
    except OSError as e:
        return False, f"Не удалось запустить PowerShell: {e}"
    m = re.search(r"BT:(\w+)(?:[ \t]+(.*))?", r.stdout or "")
    if not m:
        return False, "Не удалось управлять Bluetooth"
    result, detail = m.group(1), (m.group(2) or "").strip()
    if result == "on":
        return True, "Bluetooth включён"
    if result == "off":
        return True, "Bluetooth выключен"
    if result == "none":
        return False, "Bluetooth-адаптер не найден"
    if result == "denied":
        return False, "Windows не разрешила управлять Bluetooth (Параметры → Конфиденциальность → Радиомодули)"
    return False, f"Не удалось управлять Bluetooth: {detail}" if detail else "Не удалось управлять Bluetooth"


def bluetooth_toggle():
    """Совместимость со старым названием: переключить Bluetooth."""
    return bluetooth_set("toggle")


_profiles_cache = (0.0, [])


def wifi_profiles(max_age=30):
    """Имена сохранённых Wi-Fi сетей (к ним можно подключиться командой). Работает быстро, в отличие от сканирования."""
    global _profiles_cache
    if time.time() - _profiles_cache[0] < max_age:
        return _profiles_cache[1]
    out = _run(["netsh", "wlan", "show", "profiles"])
    names = []
    for m in re.finditer(r"(?m)^[ \t]+[^:\n]+:[ \t]*(.+?)[ \t]*$", out):  # строки вида «    Все профили пользователей : Имя»
        if m.group(1) not in names:
            names.append(m.group(1))
    _profiles_cache = (time.time(), names)
    return names
