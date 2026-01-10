# /opt/radio/modules/base_module.py

from abc import ABC, abstractmethod

class RadioModule(ABC):
    """
    Абстрактный базовый класс для всех модулей радио.
    """
    
    def __init__(self):
        """
        Конструктор по умолчанию.
        """
        self.config = {}
        self.is_system = False # По умолчанию модуль можно ставить в эфир

    @abstractmethod
    def prepare(self, event_config, context):
        pass

    def get_config_schema(self):
        """ Возвращает схему настроек для админки. """
        return {}
    
    def update_config(self, new_config):
        """ Сохраняет новые настройки. """
        self.config.update(new_config)