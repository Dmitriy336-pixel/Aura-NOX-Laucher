"""Утилиты для команд «процессы» и «убить»: список и завершение процессов (psutil, а без него tasklist/taskkill)."""
import csv
import io
import os
import subprocess
import time

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        return None


def _tasklist():
    """[(pid, имя, mem_мб)] из tasklist: запасной вариант без psutil."""
    try:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, creationflags=NO_WINDOW,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    text = out.decode("utf-8", errors="replace") if b"\x00" not in out else out.decode("utf-16", errors="replace")
    rows = []
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) < 5:
            continue
        digits = "".join(ch for ch in rec[4] if ch.isdigit())  # «12 345 КБ»
        try:
            rows.append((int(rec[1]), rec[0], int(digits) // 1024 if digits else 0))
        except ValueError:
            continue
    return rows


def top_processes(limit=10):
    """[(pid, имя, cpu% или None, mem_мб)] — самые тяжёлые по CPU (без psutil: по памяти, cpu=None).
    cpu считается как в Диспетчере задач: доля от всех ядер."""
    ps = _psutil()
    if ps is None:
        rows = [(pid, name, None, mem) for pid, name, mem in _tasklist() if pid != 0]
        rows.sort(key=lambda r: r[3], reverse=True)
        return rows[:limit]

    procs = []
    for p in ps.process_iter(["pid", "name"]):
        try:
            if p.info["pid"] == 0:  # «System Idle Process» — это свободное время, а не нагрузка
                continue
            p.cpu_percent(None)  # первый вызов только запоминает точку отсчёта
            procs.append(p)
        except (ps.NoSuchProcess, ps.AccessDenied):
            pass
    time.sleep(0.3)
    cores = ps.cpu_count() or 1
    rows = []
    for p in procs:
        try:
            cpu = p.cpu_percent(None) / cores
            mem = p.memory_info().rss // (1024 * 1024)
            rows.append((p.pid, p.info["name"] or "?", cpu, mem))
        except (ps.NoSuchProcess, ps.AccessDenied):
            pass
    rows.sort(key=lambda r: (r[2], r[3]), reverse=True)
    return rows[:limit]


def running(query="", limit=10):
    """Запущенные программы для подсказок команды «убить»: [(имя, сколько процессов, mem_мб, первый pid)].
    query: часть имени или начало PID. Сначала самые тяжёлые по памяти."""
    ps = _psutil()
    if ps is None:
        raw = _tasklist()
    else:
        raw = []
        for p in ps.process_iter(["pid", "name", "memory_info"]):
            try:
                info = p.info
                mem = (info["memory_info"].rss // (1024 * 1024)) if info["memory_info"] else 0
                raw.append((info["pid"], info["name"] or "?", mem))
            except (ps.NoSuchProcess, ps.AccessDenied):
                pass
    me = os.getpid()
    q = query.strip().lower()
    groups = {}
    for pid, name, mem in raw:
        if pid in (0, 4, me):  # Idle, System и сам лаунчер убивать нельзя/незачем
            continue
        if q and not (str(pid).startswith(q) if q.isdigit() else q in name.lower()):
            continue
        g = groups.setdefault(name, [0, 0, pid])
        g[0] += 1
        g[1] += mem
    rows = [(name, g[0], g[1], g[2]) for name, g in groups.items()]
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:limit]


def kill_by_name(name):
    """Завершить все процессы с этим именем. Возвращает (сколько_завершено, ошибка_или_None)."""
    name = name.strip()
    if not name:
        return 0, "пустое имя"
    low = name.lower()
    variants = {low} if low.endswith(".exe") else {low, low + ".exe"}
    ps = _psutil()
    if ps is not None:
        killed = denied = 0
        me = os.getpid()
        for p in ps.process_iter(["pid", "name"]):
            try:
                if p.info["pid"] != me and (p.info["name"] or "").lower() in variants:
                    p.kill()
                    killed += 1
            except ps.AccessDenied:
                denied += 1
            except ps.NoSuchProcess:
                pass
        if killed:
            return killed, None
        if denied:
            return 0, f"нет прав завершить «{name}» (запусти лаунчер от имени администратора)"
        return 0, f"процесс «{name}» не найден"
    target = name if "." in name else name + ".exe"
    result = subprocess.run(["taskkill", "/F", "/IM", target], capture_output=True, text=True,
                            creationflags=NO_WINDOW)
    if result.returncode == 0:
        return 1, None
    return 0, f"процесс «{name}» не найден или нет прав"


def kill_by_pid(pid):
    """Завершить процесс по PID. Возвращает (ok, ошибка_или_None)."""
    ps = _psutil()
    if ps is None:
        result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True,
                                creationflags=NO_WINDOW)
        return result.returncode == 0, (result.stderr.strip() or None)
    try:
        ps.Process(pid).kill()
        return True, None
    except ps.NoSuchProcess:
        return False, f"PID {pid} не найден"
    except ps.AccessDenied:
        return False, f"нет прав завершить PID {pid}"
