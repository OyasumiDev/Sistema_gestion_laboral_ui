import flet as ft
from app.views.containers.database_settings_area import DatabaseSettingsArea
from app.views.containers.navbar_container import NavBarContainer

class DatabaseSettingsView(ft.View):
    def __init__(self):
        super().__init__(route="/settings/db")
        self.navbar = NavBarContainer(is_root=True, modo_settings=True)
        self.database_area = DatabaseSettingsArea()

        self.controls = [
            ft.Row(
                controls=[
                    self.navbar,
                    self.database_area
                ],
                expand=True
            )
        ]

    def update_content(self, section: str):
        self.navbar._build()
        # En este caso siempre mostramos el área de base de datos.
