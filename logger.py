import datetime
import os
import config

def log(message):
    """Выводит сообщение в консоль и записывает в лог-файл."""
    timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    
    try:
        lines = []
        if os.path.exists(config.LOG_FILE):
            with open(config.LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        
        lines.append(full_message + "\n")
        
        # Ограничиваем размер лог-файла 50 строками
        if len(lines) > 50:
            lines = lines[-50:]
            
        with open(config.LOG_FILE, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        # Если с лог-файлом что-то не так, мы не должны останавливать радио
        print(f"{timestamp} [LOGGER ERROR] Failed to write to log file: {e}")