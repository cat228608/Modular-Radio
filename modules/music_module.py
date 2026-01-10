# /opt/radio/modules/music_module.py

import os
import queue
import random
import threading
import time
from .base_module import RadioModule
import config
import utils
import suno_source
from logger import log

music_queue = queue.Queue(maxsize=config.BUFFER_SIZE)

class MusicModule(RadioModule):
    _downloader_started = False
    
    def __init__(self):
        super().__init__() # <-- Важно: вызываем конструктор родителя
        if not MusicModule._downloader_started:
            log("⚙️ [MusicModule] Запускаю фоновый поток-загрузчик музыки...")
            downloader = threading.Thread(target=self._downloader_thread, daemon=True)
            downloader.start()
            MusicModule._downloader_started = True
            
    def get_config_schema(self):
        return {}

    def update_config(self, new_config):
        super().update_config(new_config)

    def prepare(self, event_config, context):
        log("⏳ [MusicModule] Жду готовый трек из очереди...")
        item = music_queue.get()
        return {"audio_path": item["song_path"], "meta": item["meta"], "cleanup": False}

    def _downloader_thread(self):
        track_list = []
        while True:
            if music_queue.full():
                time.sleep(2)
                continue
            if not track_list:
                log("📡 [MusicModule] Загрузчик: Получаю новый список треков...")
                new_tracks = suno_source.get_suno_tracks() or suno_source.get_local_library()
                if new_tracks:
                    random.shuffle(new_tracks)
                    track_list.extend(new_tracks)
                else:
                    log("❌ [MusicModule] Загрузчик: Нет музыки. Пауза 10 секунд.")
                    time.sleep(10)
                    continue
            track_meta = track_list.pop(0)
            if track_meta.get('is_local'):
                song_path = track_meta['url']
            else:
                safe_title = utils.sanitize_filename(track_meta['title'])
                song_path = os.path.join(config.MUSIC_DIR, f"{safe_title}_{track_meta['id']}.mp3")
                if not utils.download_file(track_meta['url'], song_path):
                    log(f"⚠️ [MusicModule] Сбой загрузки: {track_meta['title']}. Пропускаю.")
                    continue
            ready_item = {"song_path": song_path, "meta": track_meta}
            music_queue.put(ready_item)
            log(f"✅ [MusicModule] Трек готов: {track_meta['title']} (В буфере: {music_queue.qsize()}/{config.BUFFER_SIZE})")

    @staticmethod
    def peek_next_meta():
        if not music_queue.empty():
            # Доступ к очереди стал безопаснее
            try:
                return music_queue.queue[0]['meta']
            except (IndexError, KeyError):
                return None
        return None