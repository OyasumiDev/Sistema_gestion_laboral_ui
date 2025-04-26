# app/views/containers/theme_controller.py

import flet as ft
from app.helpers.class_singleton import class_singleton
from app.core.app_state import AppState

@class_singleton
class ThemeController:
    def __init__(self):
        self.page = AppState().page

        # No asumir nada: leer tema y aplicar control explícito
        stored = self.page.client_storage.get("tema_oscuro")
        if stored is None:
            # Si no hay preferencia, explícitamente usar tema claro
            self.tema_oscuro = False
            self.page.client_storage.set("tema_oscuro", False)
        else:
            self.tema_oscuro = stored

        self.apply_theme()

    def toggle(self):
        """
        Alterna explícitamente entre oscuro y claro y guarda la preferencia.
        """
        self.tema_oscuro = not self.tema_oscuro
        self.page.client_storage.set("tema_oscuro", self.tema_oscuro)
        self.apply_theme()

    def apply_theme(self):
        """
        Aplica el tema actual de manera explícita en la página.
        """
        if self.tema_oscuro:
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT

        try:
            self.page.update()
        except Exception:
            pass

    def get_colors(self) -> dict:
        """
        Retorna de forma explícita los colores de cada modo.
        """
        if self.tema_oscuro:
            # Tema oscuro
            return {
                "BG_COLOR": ft.colors.BLACK,
                "FG_COLOR": ft.colors.WHITE,
                "AVATAR_ACCENT": ft.colors.GREY,
                "DIVIDER_COLOR": ft.colors.GREY_800,
                "BTN_BG": ft.colors.GREY,  # Corregido para gris oscuro
            }
        else:
            # Tema claro
            return {
                "BG_COLOR": ft.colors.WHITE,
                "FG_COLOR": ft.colors.BLACK,
                "AVATAR_ACCENT": ft.colors.WHITE,
                "DIVIDER_COLOR": ft.colors.GREY_300,
                "BTN_BG": ft.colors.GREY_200,  # Corregido para gris claro
            }

    def get_fg_color(self) -> str:
        """
        Devuelve explícitamente solo el color de texto principal.
        """
        return self.get_colors()["FG_COLOR"]