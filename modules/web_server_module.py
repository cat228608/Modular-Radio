# /opt/radio/modules/web_server_module.py

from flask import Flask, send_from_directory, jsonify, request, make_response
import threading
import time
import os
import logging
from .base_module import RadioModule
import config

# Глушим логи Flask, чтобы не засорять консоль радио
log_flask = logging.getLogger('werkzeug')
log_flask.setLevel(logging.ERROR)

class WebServerModule(RadioModule):
    def __init__(self):
        super().__init__()
        self.is_system = True # Это системный модуль, он не играет музыку
        self.app = Flask(__name__, static_folder=config.WEB_DIR)
        self.active_visitors = {} # {ip: timestamp}
        self.cleanup_interval = 5 # Сек
        self.offline_timeout = 15 # Если нет пинга 15 сек - юзер ушел
        
        # --- НАСТРОЙКА РОУТОВ ---
        self._setup_routes()

    def get_config_schema(self):
        return {
            "port": {
                "label": "Локальный порт (для Nginx proxy_pass)",
                "type": "text",
                "default": "5005"
            }
        }

    def _setup_routes(self):
        
        @self.app.route('/')
        def index():
            # Отдаем главную страницу
            return send_from_directory(config.WEB_DIR, 'index.html')

        @self.app.route('/<path:path>')
        def serve_static(path):
            # Отдаем картинки, скрипты и т.д.
            return send_from_directory(config.WEB_DIR, path)

        @self.app.route('/api/heartbeat', methods=['POST', 'GET'])
        def heartbeat():
            # 1. Определяем реальный IP (учитываем Nginx)
            if request.headers.getlist("X-Forwarded-For"):
                user_ip = request.headers.getlist("X-Forwarded-For")[0]
            else:
                user_ip = request.remote_addr

            current_time = time.time()
            
            # 2. Обновляем время визита
            self.active_visitors[user_ip] = current_time
            
            # 3. Чистим мертвые души
            to_remove = [ip for ip, last_seen in self.active_visitors.items() 
                         if current_time - last_seen > self.offline_timeout]
            
            for ip in to_remove:
                del self.active_visitors[ip]
            
            online_count = len(self.active_visitors)
            
            # Добавляем заголовок, чтобы не кешировалось
            resp = make_response(jsonify({
                "online": online_count,
                "status": "ok"
            }))
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return resp

    def prepare(self, event_config, context):
        # Этот метод запускается один раз при старте оркестратора (как админка)
        port = int(self.config.get("port", 5005))
        
        def run_server():
            print(f"🌍 [WebServer] Запущен на порту {port} (за Nginx)")
            # host='127.0.0.1', чтобы снаружи нельзя было зайти мимо Nginx
            try:
                self.app.run(host='127.0.0.1', port=port, use_reloader=False, threaded=True)
            except Exception as e:
                print(f"❌ [WebServer] Ошибка запуска: {e}")

        # Запускаем в фоне
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        return None