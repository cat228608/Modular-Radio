import re
import os
import requests
import shutil
import json

import config
from logger import log

def sanitize_filename(name):
    """Удаляет из имени файла запрещенные символы."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def download_file(url, filepath):
    """Скачивает файл по URL, если он еще не существует."""
    if os.path.exists(filepath):
        return True
    try:
        with requests.get(url, stream=True, headers=config.SUNO_HEADERS, timeout=20) as r:
            if r.status_code == 200:
                with open(filepath, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                return True
            else:
                log(f"⚠️ Ошибка скачивания {url}, статус: {r.status_code}")
                return False
    except Exception as e:
        log(f"❌ Исключение при скачивании {url}: {e}")
        return False

def update_now_playing(track_info):
    """Обновляет JSON-файл с информацией о текущем треке."""
    data = {
        "title": track_info.get('title', 'Unknown Track'),
        "image": track_info.get('image', ''),
        "status": "live"
    }
    try:
        filepath = os.path.join(config.WEB_DIR, "now_playing.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        log(f"⚠️ Ошибка при обновлении now_playing.json: {e}")