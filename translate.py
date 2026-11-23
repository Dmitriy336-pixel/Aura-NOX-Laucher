"""Перевод текста через MyMemory API (бесплатно, без ключа, до ~1000 запросов/день).
Определение языка: если текст содержит кириллицу — переводим на английский, иначе — на русский.
При отсутствии интернета выводит сообщение об ошибке."""
import re
import urllib.request
import urllib.parse
import json
import sounds


def _has_cyrillic(text):
    return bool(re.search(r'[а-яёА-ЯЁ]', text))


def translate(text):
    """Возвращает (перевод, исходный_язык, целевой_язык) или (None, None, сообщение_об_ошибке)."""
    if not text.strip():
        return None, None, "пустой текст"
    src = "ru" if _has_cyrillic(text) else "en"
    tgt = "en" if src == "ru" else "ru"
    url = (
        "https://api.mymemory.translated.net/get?q="
        + urllib.parse.quote(text[:500])
        + f"&langpair={src}|{tgt}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "launcher/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        result = data.get("responseData", {}).get("translatedText", "")
        if not result or result.lower() == text.lower():
            return None, src, "не удалось перевести"
        return result, src, tgt
    except OSError:
        sounds.play("error")
        return None, None, "нет подключения к интернету"
    except Exception as e:
        sounds.play("error")
        return None, None, str(e)[:80]


def weather(city):
    """Получить погоду через wttr.in (JSON, без ключа).
    Возвращает (строка_описание) или (None, сообщение_об_ошибке)."""
    if not city.strip():
        return None, "укажи город: погода Москва"
    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "launcher/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        cur = data["current_condition"][0]
        temp_c = cur["temp_C"]
        feels = cur["FeelsLikeC"]
        desc_list = cur.get("weatherDesc", [{}])
        desc = desc_list[0].get("value", "") if desc_list else ""
        wind = cur.get("windspeedKmph", "?")
        humidity = cur.get("humidity", "?")
        # следующие дни
        days = data.get("weather", [])[:3]
        forecast = []
        for d in days:
            date = d["date"]
            hi = d["maxtempC"]
            lo = d["mintempC"]
            forecast.append(f"{date}: {lo}…{hi}°C")
        summary = (
            f"{city}: {temp_c}°C, ощущается {feels}°C, {desc.lower()}\n"
            f"Ветер: {wind} км/ч, влажность: {humidity}%"
        )
        if forecast:
            summary += "\nПрогноз: " + "  |  ".join(forecast)
        return summary, None
    except OSError:
        sounds.play("error")
        return None, "нет подключения к интернету"
    except Exception as e:
        sounds.play("error")
        return None, f"ошибка: {e}"
