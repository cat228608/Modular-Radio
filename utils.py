# /opt/radio/utils.py

import os
import json
import config
from logger import log

def update_now_playing(track_info):
    """
    Обновляет JSON-файл с информацией о текущем треке.
    Используется Оркестратором для обновления статуса на сайте.
    """
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
        log(f"⚠️ [Utils] Ошибка при обновлении now_playing.json: {e}")