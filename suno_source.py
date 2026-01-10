# /opt/radio/suno_source.py

import os
import requests
import config
from logger import log

def get_suno_tracks():
    """Получает список трендовых треков с API Suno, используя актуальную структуру JSON."""
    payload = {
        "start_index": 0, "page_size": 25,
        "section_name": "trending_songs", "section_content": "Global",
        "secondary_section_content": "Now", "page": 1, "disable_shuffle": False
    }
    try:
        # Собираем заголовки для запроса
        headers = config.SUNO_HEADERS.copy()
        # Убеждаемся, что в конфиге токен БЕЗ слова "Bearer"
        headers['authorization'] = f"Bearer {headers['authorization']}"

        response = requests.post(
            config.SUNO_API_URL,
            headers=headers,
            json=payload,
            timeout=15 # Увеличим таймаут на всякий случай
        )

        if response.status_code != 200:
            log(f"❌ Suno API вернул ошибку: Статус {response.status_code}, Ответ: {response.text[:200]}")
            return []

        data = response.json()
        tracks = []
        
        # Проверяем, что ответ содержит нужные нам секции и элементы
        if 'sections' in data and data['sections'] and 'items' in data['sections'][0]:
            items = data['sections'][0]['items']
        else:
            log("🤔 Suno API не вернул ожидаемую структуру 'sections' -> 'items'.")
            return []

        for item in items:
            # Данные трека находятся прямо в 'item', без вложенного 'clip'
            if isinstance(item, dict):
                audio_url = item.get('audio_url')
                title = item.get('title', 'Unknown Title')
                song_id = item.get('id')
                image_url = item.get('image_large_url') or item.get('image_url')

                if audio_url and song_id:
                    tracks.append({
                        'title': title, 'url': audio_url,
                        'id': song_id, 'image': image_url
                    })
        
        if not tracks:
             log("⚠️ Не удалось извлечь данные о треках из ответа API, хотя элементы были найдены.")

        return tracks

    except requests.exceptions.RequestException as e:
        log(f"❌ Сетевая ошибка при запросе к Suno API: {e}")
        return []
    except Exception as e:
        log(f"❌ Непредвиденная ошибка при обработке ответа от Suno API: {e}")
        return []


def get_local_library():
    """Сканирует папку MUSIC_DIR и возвращает список локальных треков."""
    try:
        files = [f for f in os.listdir(config.MUSIC_DIR) if f.endswith(".mp3")]
        tracks = []
        for f in files:
            if "dj_" in f: continue
            tracks.append({
                'title': os.path.splitext(f)[0],
                'url': os.path.join(config.MUSIC_DIR, f),
                'id': f, 'image': '', 'is_local': True
            })
        return tracks
    except FileNotFoundError:
        log(f"⚠️ Папка с музыкой {config.MUSIC_DIR} не найдена. Создайте ее.")
        return []
    except Exception as e:
        log(f"❌ Ошибка при сканировании локальной библиотеки: {e}")
        return []