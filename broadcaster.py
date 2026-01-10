# /opt/radio/broadcaster.py

import subprocess
import os
import time
import config
from logger import log

_ffmpeg_process = None

def start_stream():
    """Запускает FFmpeg один раз, ожидая данные через stdin (трубу)."""
    global _ffmpeg_process
    
    # Убиваем старый процесс, если он есть
    if _ffmpeg_process and _ffmpeg_process.poll() is None:
        try:
            _ffmpeg_process.terminate()
            _ffmpeg_process.wait(timeout=2)
        except:
            _ffmpeg_process.kill()

    command = [
        config.FFMPEG_PATH,
        '-re',
        '-f', 'mp3',
        '-i', 'pipe:0',  # Читаем из stdin
        '-acodec', 'libmp3lame',
        '-ab', '320k',
        '-ar', '44100',
        '-q:a', '0', 
        '-content_type', 'audio/mpeg',
        '-ice_name', 'Mafioznik Radio',
        '-ice_description', 'Non-stop AI Music',
        '-f', 'mp3',
        f'icecast://source:{config.ICECAST_PASSWORD}@{config.ICECAST_HOST}:{config.ICECAST_PORT}{config.MOUNT_POINT}'
    ]
    
    log("🎙️ Запуск основного процесса вещания FFmpeg...")
    _ffmpeg_process = subprocess.Popen(
        command, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )

def feed_to_stream(filepath):
    """Отправляет аудиофайл в запущенный процесс FFmpeg."""
    global _ffmpeg_process
    
    if not os.path.exists(filepath):
        log(f"⚠️ Файл не найден: {filepath}")
        return

    # Проверяем размер
    if os.path.getsize(filepath) < 1000:
        log(f"⚠️ Файл слишком маленький (битый?): {filepath}. Пропускаю.")
        return

    # Проверяем, жив ли FFmpeg
    if _ffmpeg_process is None or _ffmpeg_process.poll() is not None:
        log("⚠️ FFmpeg упал, перезапускаем...")
        start_stream()
        time.sleep(1) # Даем ему секунду на старт

    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(4096)
                if not chunk: break
                
                try:
                    _ffmpeg_process.stdin.write(chunk)
                    _ffmpeg_process.stdin.flush()
                except (BrokenPipeError, IOError):
                    log("❌ Ошибка записи в FFmpeg (Broken Pipe). Перезапуск потока.")
                    start_stream()
                    # Пробуем дослать остаток файла в новый поток, или просто выходим
                    return 
                    
    except Exception as e:
        log(f"❌ Ошибка передачи данных: {e}")