# app/views/empleados_view.py

import flet as ft
from app.views.containers.empleados_container import EmpleadosContainer

class EmpleadosView(ft.View):
    """Vista de Empleados"""
    def __init__(self):
        super().__init__(
            route="/home/empleados",
            controls=[
                EmpleadosContainer()
            ]
        )
