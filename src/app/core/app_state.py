import flet as ft

class AppState:
    def __init__(self):
        self.page: ft.Page = None
        self.data = {}

    def set(self, key, value):
        self.data[key] = value

    def get(self, key, default = None):
        return self.data.get(key, default)

state = AppState()