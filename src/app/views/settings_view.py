# app/views/settings_view.py

import flet as ft
from app.views.containers.navbar_container import NavBarContainer
from app.views.containers.database_settings_area import DatabaseSettingsArea  # <-- Importa tu área de DB

class SettingsView(ft.View):
    def __init__(self):
        super().__init__(route="/settings")
        self.navbar = NavBarContainer(is_root=True, modo_settings=True)
        self.content_area = ft.Container(expand=True)

        self.controls = [
            ft.Row(
                [
                    self.navbar,
                    self.content_area
                ],
                expand=True
            )
        ]

        # Carga inicial
        self.update_content("settings")

    def update_content(self, section: str):
        self.navbar._build()  # 🔥 Siempre actualizar los colores si cambia el tema
        
        if section in ["settings", "db"]:
            self.content_area.content = DatabaseSettingsArea()
        else:
            self.content_area.content = ft.Text(f"Settings sección: {section}", size=20)
