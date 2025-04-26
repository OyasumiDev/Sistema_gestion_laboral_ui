# app/views/settings_view.py

import flet as ft
from app.views.containers.settings_navbar_container import SettingsNavBarContainer
from app.core.app_state import AppState
from app.views.containers.theme_controller import ThemeController

class SettingsView(ft.View):
    def __init__(self):
        super().__init__(route="/settings", controls=[])

        self.page = AppState().page
        self.theme_ctrl = ThemeController()

        # Barra lateral tipo settings
        self.nav_bar = SettingsNavBarContainer()

        # Área de contenido dinámico
        self.content_area = ft.Container(expand=True)

        # Layout principal
        layout = ft.Row(
            expand=True,
            controls=[self.nav_bar, self.content_area]
        )
        self.controls.append(layout)

        # Contenido inicial
        self.update_content("database")

    def update_content(self, section: str):
        # Refrescar NavBar si el tema cambió
        if hasattr(self.nav_bar, "build"):
            self.nav_bar.build()

        # Obtener colores desde el singleton
        colors = self.theme_ctrl.get_colors()
        fg_color = colors["FG_COLOR"]

        # Lógica de contenido
        if section == "database":
            content_text = "Gestión de base de datos (importar/exportar)"
        else:
            content_text = "Vista no encontrada."

        # Actualizar el área de contenido
        self.content_area.content = ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Text(content_text, size=16, color=fg_color)
        )

        # Refrescar página
        self.page.update()
