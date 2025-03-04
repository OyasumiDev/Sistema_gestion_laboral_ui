import flet as ft
from app.helpers.class_singleton import class_singleton

@class_singleton
class AppState:
    """
    Clase para manejar el estado de la app
    """
    def __init__(self):
        self.page: ft.Page = None
        self.data = {}

    def set(self, key, value):
        """
        Setea un dato
        :param key:
        :param value:
        :return:
        """
        self.data[key] = value

    def get(self, key, default = None):
        """
        Obtiene un dato
        :param key:
        :param default:
        :return:
        """
        return self.data.get(key, default)