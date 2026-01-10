# /opt/radio/config.py

import os

# --- НАСТРОЙКИ ICECAST ---
ICECAST_HOST = "localhost"
ICECAST_PORT = "8000"
ICECAST_PASSWORD = "hackme" #ICECAST пароль
MOUNT_POINT = "/stream"

# --- СИСТЕМНЫЕ ПУТИ ---
FFMPEG_PATH = "/usr/bin/ffmpeg"
BASE_DIR = "/opt/radio"
MUSIC_DIR = os.path.join(BASE_DIR, "music")
WEB_DIR = os.path.join(BASE_DIR, "web")
LOG_FILE = os.path.join(WEB_DIR, "logs.txt")

# --- НАСТРОЙКИ ВЕЩАНИЯ ---
BUFFER_SIZE = 3  # Сколько треков готовить заранее

# --- НАСТРОЙКИ SUNO API ---
SUNO_API_URL = "https://studio-api.prod.suno.com/api/discover"
HEADERS = {
    'accept': '*/*',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'authorization': 'Bearer ', #Ваш токен суно
    'content-type': 'application/json',
    'origin': 'https://suno.com',
    'referer': 'https://suno.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'device-id': '7b0811a2-2' #Dfi шв lbdfqcf
}

HEADERS = {
    'accept': '*/*',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'authorization': 'Bearer ', #Ваш токен суно
    'content-type': 'application/json',
    'origin': 'https://suno.com',
    'referer': 'https://suno.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'device-id': '7b0811a2-2' #Dfi шв lbdfqcf
}

# --- НАСТРОЙКИ DJ ---
DJ_VOICE = "ru-RU-DmitryNeural"  # Голос для edge-tts
DJ_CHANCE_TO_SPEAK_FACT = 0.5    # 50% шанс рассказать факт

# Убедимся, что папки существуют при старте
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)