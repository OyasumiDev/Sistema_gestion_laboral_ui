import flet as ft

class EmpleadosView(ft.View):
    """Vista de Empleados"""
    def __init__(self):
        super().__init__(
            route="/home/empleados",
            controls=[
                ft.Text("Vista de Empleados", size=20)
            ]
        )
