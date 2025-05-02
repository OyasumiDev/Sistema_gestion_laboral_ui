# app/views/database_settings_view.py
import flet as ft
from app.views.containers.navbar_container import NavBarContainer   
from app.views.containers.database_settings_area import DatabaseSettingsArea    

class DatabaseSettingsView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__(route="/settings/db")
        self.page = page
        self.navbar = NavBarContainer(is_root=True, modo_settings=True)
        self.database_area = DatabaseSettingsArea(self.page)  # 👈 Pasar el page aquí
        self.controls = [
            ft.Row(
                controls=[
                    self.navbar,
                    self.database_area
                ],
                expand=True
            )
        ]
