# /opt/radio/modules/dj_module.py

import os
import random
import time
import subprocess
import re
from gtts import gTTS  # Библиотека Google TTS
from .base_module import RadioModule
from logger import log

# Импортируем значения по умолчанию из файла данных
# (Убедитесь, что dj_data.py существует и содержит эти переменные)
from dj_data import (
    DEFAULT_INTROS_STR, 
    DEFAULT_TRANSITIONS_STR, 
    DEFAULT_INTROS_LIST, 
    DEFAULT_TRANSITIONS_LIST
)

class DjModule(RadioModule):
    """
    Модуль DJ. Генерирует подводки к трекам, используя разные TTS движки
    и подмешивая интересные факты из модуля Facts.
    """
    
    def __init__(self):
        super().__init__()
    
    def get_config_schema(self):
        return {
            "engine": {
                "label": "TTS Движок (Синтезатор)",
                "type": "select",
                "options": ["edge-tts", "google"],
                "default": "edge-tts"
            },
            "voice": {
                "label": "Голос (Только для edge-tts)",
                "type": "select",
                "options": ["ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"],
                "default": "ru-RU-DmitryNeural"
            },
            "fact_chance": {
                "label": "Шанс факта (0.0 - 1.0)",
                "type": "text", 
                "default": "0.5"
            },
            "facts_module_name": {
                "label": "Имя модуля фактов (системное)",
                "type": "text",
                "default": "facts"
            },
            "intros": {
                "label": "Шаблоны INTRO (одна строка - одна фраза)",
                "type": "textarea",
                "default": DEFAULT_INTROS_STR
            },
            "transitions": {
                "label": "Шаблоны с ФАКТАМИ (используйте {fact} и {title})",
                "type": "textarea",
                "default": DEFAULT_TRANSITIONS_STR
            }
        }

    def _clean_text_for_tts(self, text):
        """
        Удаляет символы, которые могут сломать генерацию или звучат плохо.
        """
        if not text: return ""
        text = str(text)
        # Заменяем типографику
        text = text.replace('«', '"').replace('»', '"')
        text = text.replace('—', '-')
        # Удаляем невидимые управляющие символы
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _generate_speech_file(self, text, engine, voice):
        """
        Генерирует MP3 файл с речью, используя выбранный движок.
        """
        clean_text = self._clean_text_for_tts(text)
        if not clean_text:
            log("⚠️ [DjModule] Пустой текст для озвучки.")
            return None
        
        output_filename = os.path.join("channel", f"dj_{int(time.time())}.mp3")
        log(f"🗣️ DJ ({engine}): {clean_text}")

        try:
            # --- ДВИЖОК 1: EDGE-TTS (Microsoft Azure Free) ---
            if engine == "edge-tts":
                command = [
                    "edge-tts",
                    "--voice", voice,
                    "--text", clean_text,
                    "--write-media", output_filename,
                    "--rate=+5%" # Немного ускоряем для динамики
                ]
                # Запускаем внешний процесс с таймаутом
                subprocess.run(
                    command, 
                    check=True, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL, 
                    timeout=20
                )
                return output_filename

            # --- ДВИЖОК 2: GOOGLE TTS (gTTS) ---
            elif engine == "google":
                # Работает внутри Python, голос по умолчанию
                tts = gTTS(text=clean_text, lang='ru', slow=False)
                tts.save(output_filename)
                return output_filename
            
            else:
                log(f"❌ [DjModule] Неизвестный движок: {engine}")
                return None

        except subprocess.TimeoutExpired:
            log(f"❌ [DjModule] Ошибка: {engine} завис (timeout).")
            return None
        except Exception as e:
            log(f"❌ [DjModule] Ошибка генерации ({engine}): {e}")
            return None

    def prepare(self, event_config, context):
        """
        Основной метод, вызываемый Оркестратором.
        """
        # 1. Читаем настройки из конфига (или берем дефолтные)
        engine = self.config.get("engine", "edge-tts")
        voice = self.config.get("voice", "ru-RU-DmitryNeural")
        try:
            fact_chance = float(self.config.get("fact_chance", 0.5))
        except (ValueError, TypeError):
            fact_chance = 0.5

        # 2. Определяем, что говорить (текст или шаблон)
        mode = event_config.get("mode", "intro")
        custom_text = event_config.get("text")
        
        final_text = ""

        # --- СЦЕНАРИЙ 1: Пользовательский текст (Custom) ---
        if custom_text:
            final_text = custom_text
        
        # --- СЦЕНАРИЙ 2: Подводка к следующему треку (Intro) ---
        elif mode == "intro":
            next_track_title = context.get("next_track_title", "следующий трек")
            
            # Получаем списки шаблонов из настроек
            raw_intros = self.config.get("intros", "")
            intros_list = [l.strip() for l in raw_intros.split('\n') if l.strip()]
            if not intros_list: intros_list = DEFAULT_INTROS_LIST

            raw_trans = self.config.get("transitions", "")
            trans_list = [l.strip() for l in raw_trans.split('\n') if l.strip()]
            if not trans_list: trans_list = DEFAULT_TRANSITIONS_LIST

            # Решаем, говорить факт или нет
            if random.random() < fact_chance:
                # Пытаемся получить факт из модуля FactsModule
                fact_text = None
                target_module_name = self.config.get("facts_module_name", "facts")
                all_modules = context.get("all_modules", {})
                
                facts_module = all_modules.get(target_module_name)
                
                if facts_module and hasattr(facts_module, "get_random_fact"):
                    fact_text = facts_module.get_random_fact()
                
                if fact_text:
                    # Есть факт -> используем шаблон переходов
                    template = random.choice(trans_list)
                    final_text = template.replace("{fact}", fact_text).replace("{title}", next_track_title)
                else:
                    # Нет факта -> используем обычное интро
                    template = random.choice(intros_list)
                    final_text = template.replace("{title}", next_track_title)
            else:
                # Шанс не выпал -> используем обычное интро
                template = random.choice(intros_list)
                final_text = template.replace("{title}", next_track_title)
        
        # --- СЦЕНАРИЙ 3: Завершение (Outro) ---
        elif mode == "outro":
            last_meta = context.get('last_track_meta')
            title = last_meta.get('title') if last_meta else "хороший трек"
            final_text = f"Только что прозвучал {title}. Продолжаем эфир!"

        # 3. Если текст пустой, ничего не делаем
        if not final_text:
            return None
        
        # 4. Генерируем аудиофайл
        audio_path = self._generate_speech_file(final_text, engine, voice)
        
        if audio_path:
            return {
                "audio_path": audio_path,
                "meta": {
                    "title": "Mafioznik DJ", 
                    "image": "https://cdn-o.suno.com/Logo-7.svg"
                },
                "cleanup": True # Файл временный, после эфира удалить
            }
            
        return None