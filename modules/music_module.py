# /opt/radio/modules/music_module.py

import os
import queue
import random
import threading
import time
import requests
import re
import shutil
from .base_module import RadioModule
import config
from logger import log

# Очередь (буфер) для готовых треков
music_queue = queue.Queue(maxsize=config.BUFFER_SIZE)

class MusicModule(RadioModule):
    _downloader_started = False
    
    def __init__(self):
        super().__init__()
        # Базовые заголовки, если в конфиге пусто
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://suno.com/'
        }
        
        if not MusicModule._downloader_started:
            log("⚙️ [MusicModule] Инициализация загрузчика...")
            downloader = threading.Thread(target=self._downloader_thread, daemon=True)
            downloader.start()
            MusicModule._downloader_started = True

    def get_config_schema(self):
        return {
            "suno_api_url": {
                "label": "Suno API URL",
                "type": "text",
                "default": "https://studio-api.prod.suno.com/api/discover"
            },
            "auth_token": {
                "label": "Authorization Token (без Bearer)",
                "type": "textarea",
                "default": ""
            },
            "cookie": {
                "label": "Cookie (если требуется)",
                "type": "textarea",
                "default": ""
            },
            "user_agent": {
                "label": "User-Agent",
                "type": "text",
                "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "use_local_backup": {
                "label": "Играть локальные файлы при ошибке API?",
                "type": "select",
                "options": ["yes", "no"],
                "default": "yes"
            }
        }

    def prepare(self, event_config, context):
        """Метод вызывается Оркестратором, когда пора играть музыку."""
        log("⏳ [MusicModule] Ожидание трека из буфера...")
        # Блокируем поток, пока в очереди не появится трек
        item = music_queue.get()
        return {"audio_path": item["song_path"], "meta": item["meta"], "cleanup": False}

    # --- ВНУТРЕННИЕ МЕТОДЫ (Ранее были в suno_source и utils) ---

    def _get_headers(self):
        """Собирает заголовки на основе настроек из админки."""
        headers = self.default_headers.copy()
        
        # User-Agent
        ua = self.config.get("user_agent", "").strip()
        if ua: headers['User-Agent'] = ua

        # Auth Token
        token = self.config.get("auth_token", "").strip()
        if token:
            # Убираем дублирование слова Bearer
            if token.lower().startswith("bearer "):
                headers['Authorization'] = token
            else:
                headers['Authorization'] = f"Bearer {token}"
        
        # Cookie
        cookie = self.config.get("cookie", "").strip()
        if cookie: headers['Cookie'] = cookie
            
        return headers

    def _sanitize_filename(self, name):
        """Убирает плохие символы из имени файла."""
        return re.sub(r'[\\/*?:"<>|]', "", name)

    def _download_file(self, url, filepath):
        """Скачивает файл с учетом заголовков модуля."""
        if os.path.exists(filepath):
            return True
            
        try:
            # Используем заголовки модуля (важно, если Suno включит защиту на CDN)
            headers = self._get_headers()
            
            # Таймаут 30 сек на скачивание
            with requests.get(url, stream=True, headers=headers, timeout=30) as r:
                if r.status_code == 200:
                    with open(filepath, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)
                    return True
                else:
                    log(f"⚠️ [MusicModule] Ошибка скачивания {url}: HTTP {r.status_code}")
                    return False
        except Exception as e:
            log(f"❌ [MusicModule] Исключение при скачивании: {e}")
            return False

    def _fetch_suno_tracks(self):
        """Запрашивает список треков у API."""
        url = self.config.get("suno_api_url", "https://studio-api.prod.suno.com/api/discover")
        headers = self._get_headers()

        payload = {
            "start_index": 0, "page_size": 25,
            "section_name": "trending_songs", "section_content": "Global",
            "secondary_section_content": "Now", "page": 1, "disable_shuffle": False
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code != 200:
                log(f"❌ [MusicModule] Ошибка API Suno: {response.status_code}. Проверьте токен!")
                return []

            data = response.json()
            tracks = []
            
            # Разбор JSON структуры Suno
            if 'sections' in data and data['sections'] and 'items' in data['sections'][0]:
                items = data['sections'][0]['items']
                for item in items:
                    if isinstance(item, dict):
                        audio_url = item.get('audio_url')
                        title = item.get('title', 'Unknown Title')
                        song_id = item.get('id')
                        image_url = item.get('image_large_url') or item.get('image_url')

                        if audio_url and song_id:
                            tracks.append({
                                'title': title, 'url': audio_url,
                                'id': song_id, 'image': image_url,
                                'is_local': False
                            })
            return tracks

        except Exception as e:
            log(f"❌ [MusicModule] Ошибка соединения с API: {e}")
            return []

    def _get_local_tracks(self):
        """Резервный источник: локальная папка."""
        try:
            files = [f for f in os.listdir(config.MUSIC_DIR) if f.endswith(".mp3")]
            tracks = []
            for f in files:
                # Игнорируем файлы, созданные DJ или рекламой
                if f.startswith("dj_") or f.startswith("ad_") or f.startswith("news_"): 
                    continue
                    
                tracks.append({
                    'title': os.path.splitext(f)[0],
                    'url': os.path.join(config.MUSIC_DIR, f),
                    'id': f, 'image': '', 'is_local': True
                })
            return tracks
        except Exception:
            return []

    def _downloader_thread(self):
        """Фоновый процесс: следит за буфером и качает музыку."""
        track_list = []
        
        while True:
            # 1. Если буфер полон, спим
            if music_queue.full():
                time.sleep(2)
                continue

            # 2. Если список воспроизведения пуст, получаем новый
            if not track_list:
                log("📡 [MusicModule] Обновление плейлиста...")
                
                # Пробуем API
                new_tracks = self._fetch_suno_tracks()
                
                # Если API пусто, пробуем локалку (если разрешено)
                if not new_tracks and self.config.get("use_local_backup", "yes") == "yes":
                    log("⚠️ [MusicModule] API недоступен. Переход на локальную библиотеку.")
                    new_tracks = self._get_local_tracks()

                if new_tracks:
                    random.shuffle(new_tracks)
                    track_list.extend(new_tracks)
                    log(f"✅ [MusicModule] Загружено в список: {len(new_tracks)} треков.")
                else:
                    log("❌ [MusicModule] Нет доступных треков. Пауза 30 сек.")
                    time.sleep(30)
                    continue

            # 3. Берем трек из списка и готовим файл
            track_meta = track_list.pop(0)
            
            if track_meta.get('is_local'):
                # Локальный файл уже на диске
                ready_item = {"song_path": track_meta['url'], "meta": track_meta}
                music_queue.put(ready_item)
                log(f"💿 [MusicModule] Локальный файл добавлен в очередь: {track_meta['title']}")
            else:
                # Удаленный файл надо скачать
                safe_title = self._sanitize_filename(track_meta['title'])
                # Ограничиваем длину имени файла, чтобы не было ошибок ОС
                safe_title = safe_title[:50] 
                filename = f"{safe_title}_{track_meta['id']}.mp3"
                song_path = os.path.join(config.MUSIC_DIR, filename)
                
                log(f"📥 [MusicModule] Скачивание: {track_meta['title']}...")
                if self._download_file(track_meta['url'], song_path):
                     ready_item = {"song_path": song_path, "meta": track_meta}
                     music_queue.put(ready_item)
                     log(f"✅ [MusicModule] Готово. В буфере: {music_queue.qsize()}/{config.BUFFER_SIZE}")
                else:
                    log(f"⚠️ [MusicModule] Пропуск трека (ошибка загрузки).")
                    continue

    @staticmethod
    def peek_next_meta():
        """Позволяет DJ подсмотреть следующий трек."""
        if not music_queue.empty():
            try:
                return music_queue.queue[0]['meta']
            except:
                return None
        return None