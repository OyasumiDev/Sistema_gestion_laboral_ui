import flet as ft
from typing import Any

class WindowMain:

    def __init__(self):
        self._page = None

    def __call__(self, flet_page: ft.Page) -> Any:
        self._page = flet_page
        self._page.title = "Sistema de gestion"
        self._page.window.center()
        self._page.padding = 0
        self._page.theme_mode = ft.ThemeMode.LIGHT
        self._page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE_ACCENT_100)
        self._page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self._page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    def page_update(self):
        ''''
        Actualiza la informacion dentro de la ui
        '''
        try:
            self._page.update()
        except Exception as e:
            pass


window_main = WindowMain()