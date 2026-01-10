# /opt/radio/radio_orchestrator.py

import os
import json
import time
import importlib
import threading

import config
import utils
import broadcaster
from logger import log
from modules import music_module

SETTINGS_FILE = "module_settings.json"
SCHEDULE_FILE = "schedule.json"

def load_modules():
    modules = {}
    for filename in os.listdir("modules"):
        if filename.endswith("_module.py"):
            module_name_key = filename.replace("_module.py", "")
            module_import_name = filename[:-3]
            class_name = "".join([s.capitalize() for s in module_import_name.split('_')])
            try:
                module_spec = importlib.import_module(f"modules.{module_import_name}")
                module_class = getattr(module_spec, class_name)
                modules[module_name_key] = module_class()
                log(f"✅ Модуль '{module_name_key}' успешно загружен.")
            except Exception as e:
                log(f"❌ Не удалось загрузить модуль {module_import_name}: {e}")
    return modules

def load_settings(modules):
    settings = {}
    for name, module in modules.items():
        schema = module.get_config_schema()
        if schema:
            settings[name] = {key: props.get('default', '') for key, props in schema.items()}
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved_settings = json.load(f)
                for module_name, module_settings in saved_settings.items():
                    if module_name in settings:
                        settings[module_name].update(module_settings)
            log("🔧 Сохраненные настройки модулей загружены.")
        except Exception as e:
            log(f"⚠️ Не удалось загрузить {SETTINGS_FILE}: {e}")
    
    return settings

def main():
    log("🚀 --- MAFIOZNIK RADIO ORCHESTRATOR v3.1 (Modular) --- 🚀")
    
    # 1. Загружаем все модули из папки modules/
    modules = load_modules()
    if not modules: 
        log("❌ Ошибка: Не найдено ни одного модуля.")
        return
        
    # 2. Загружаем сохраненные настройки и применяем их
    settings = load_settings(modules)
    for name, module_settings in settings.items():
        if name in modules:
            modules[name].update_config(module_settings)

    # 3. --- ЗАПУСК АДМИН-ПАНЕЛИ ---
    if 'admin_panel' in modules:
        admin_handler = modules['admin_panel']
        # Передаем модули и настройки в админку, чтобы она могла ими управлять
        admin_context = {'all_modules': modules, 'all_settings': settings}
        
        # Запускаем в фоновом daemon-потоке
        admin_thread = threading.Thread(
            target=admin_handler.prepare, 
            args=(None, admin_context), 
            daemon=True
        )
        admin_thread.start()
        log("🔐 Админ-панель запущена на http://<ваш_ip>:8080/admin")
    else:
        log("⚠️ Модуль 'admin_panel' не найден. Веб-интерфейс недоступен.")
        
    if 'web_server' in modules:
        # Запускаем веб-сервер в фоне
        web_thread = threading.Thread(
            target=modules['web_server'].prepare, 
            args=(None, {}), 
            daemon=True
        )
        web_thread.start()
        log("🌍 Модуль WebServer активирован.")
    else:
        log("⚠️ Файл modules/web_server_module.py не найден.")
        
    # 4. --- ОСНОВНОЙ ЦИКЛ ВЕЩАНИЯ ---
    broadcaster.start_stream()
    schedule = []
    schedule_index = 0
    last_played_meta = None

    while True:
        # Перезагружаем расписание, когда цикл доходит до начала
        if schedule_index == 0:
            try:
                with open(SCHEDULE_FILE, "r", encoding="utf-8") as f: 
                    schedule = json.load(f)
                log(f"📜 Расписание обновлено: {len(schedule)} событий.")
            except Exception as e:
                log(f"⚠️ Ошибка чтения {SCHEDULE_FILE}: {e}.")
                if not schedule:
                    log("❌ Расписание пустое. Жду 60 сек...")
                    time.sleep(60)
                    continue
        
        # Получаем текущее событие
        event = schedule[schedule_index]
        event_type = event.get("type")
        handler = modules.get(event_type)
        
        if not handler:
            log(f"⚠️ Пропускаю событие: нет модуля для типа '{event_type}'.")
        else:
            log(f"▶️  Обработка события: {event_type.upper()}")
            
            # --- СОБИРАЕМ КОНТЕКСТ ---
            # Это данные, которые передаются модулю для работы.
            # ВАЖНО: передаем 'all_modules', чтобы DJ мог найти модуль Facts.
            context = {
                'last_track_meta': last_played_meta,
                'all_modules': modules 
            }
            
            # Пытаемся узнать, какой трек будет следующим (для DJ Intro)
            next_index = (schedule_index + 1) % len(schedule)
            if schedule[next_index].get("type") == "music":
                if 'music' in modules and hasattr(modules['music'], 'peek_next_meta'):
                    next_meta = modules['music'].peek_next_meta()
                    if next_meta: 
                        context['next_track_title'] = next_meta.get('title', 'следующий трек')

            # --- ЗАПУСК МОДУЛЯ ---
            try:
                result = handler.prepare(event, context)
                
                # Если модуль вернул аудиофайл — играем его
                if result and result.get("audio_path") and os.path.exists(result["audio_path"]):
                    
                    # Обновляем метаданные на сайте (now_playing.json)
                    utils.update_now_playing(result["meta"])
                    log(f"🎙️ В ЭФИРЕ: {result['meta']['title']}")
                    
                    # Отправляем аудио в FFmpeg
                    broadcaster.feed_to_stream(result["audio_path"])
                    
                    # Запоминаем, что играло (если это музыка)
                    if event_type == "music": 
                        last_played_meta = result.get("meta")
                    
                    # Удаляем временный файл, если модуль попросил (cleanup=True)
                    if result.get("cleanup"):
                        try: 
                            os.remove(result["audio_path"])
                        except OSError as e: 
                            log(f"⚠️ Ошибка удаления файла: {e}")
                
                elif handler and not getattr(handler, 'is_system', False):
                    # Если модуль не вернул файл и это не системный модуль (как facts)
                    log(f"ℹ️ Модуль {event_type.upper()} завершил работу без аудио.")
                    
            except Exception as e:
                log(f"❌ Критическая ошибка в модуле {event_type}: {e}")

        # Переход к следующему событию
        schedule_index = (schedule_index + 1) % len(schedule)

if __name__ == "__main__":
    main()