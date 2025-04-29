# app/views/asistencias_view.py

import flet as ft
from app.views.containers.asistencias_container import AsistenciasContainer

class AsistenciasView(ft.View):
    """Vista de Asistencias"""
    def __init__(self):
        super().__init__(
            route="/home/asistencias",
            controls=[
                AsistenciasContainer()
            ]
        )
