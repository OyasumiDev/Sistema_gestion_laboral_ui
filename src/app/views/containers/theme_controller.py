# app/views/containers/theme_controller.py
import flet as ft
from app.helpers.class_singleton import class_singleton
from app.core.app_state import AppState

@class_singleton
class ThemeController:
    def __init__(self):
        # Obtiene la misma instancia de Page almacenada en WindowMain
        self.page = AppState().page

        # Lee tema almacenado y asigna True si viene None
        stored = self.page.client_storage.get("tema_oscuro")
        self.tema_oscuro = stored if stored is not None else True

        # Aplica el tema inicial
        self.apply_theme()

    def toggle(self):
        # Cambia y persiste
        self.tema_oscuro = not self.tema_oscuro
        self.page.client_storage.set("tema_oscuro", self.tema_oscuro)
        self.apply_theme()

    def apply_theme(self):
        # Ajusta el modo y refresca
        self.page.theme_mode = (
            ft.ThemeMode.DARK if self.tema_oscuro else ft.ThemeMode.LIGHT
        )
        self.page.update()
