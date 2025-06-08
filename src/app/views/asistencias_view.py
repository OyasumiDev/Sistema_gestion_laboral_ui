# app/views/asistencias_view.py

import flet as ft
from app.core.app_state import AppState
from app.views.containers.asistencias_container import AsistenciasContainer
from app.views.nvar_view import NavBarView

class AsistenciasView(ft.View):
    """Vista de Asistencias"""
    def __init__(self):
        super().__init__(route="/home/asistencias", controls=[])

        state = AppState()
        page = state.page

        user_data = page.client_storage.get("app.user")
        is_root = user_data and user_data.get("role") == "root"

        nav_bar = NavBarView(is_root=is_root)
        content_area = AsistenciasContainer()

        layout = ft.Row(
            expand=True,
            controls=[
                nav_bar,
                ft.Container(
                    content=content_area,
                    expand=True,
                    alignment=ft.alignment.top_center,
                    padding=20
                )
            ]
        )

        self.controls.append(layout)
