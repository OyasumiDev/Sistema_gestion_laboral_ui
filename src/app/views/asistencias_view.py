import flet as ft

class AsistenciasView(ft.View):
    """Vista de Asistencias"""
    def __init__(self):
        super().__init__(
            route="/home/asistencias",
            controls=[
                ft.Text("Vista de Asistencias", size=20)
            ]
        )
        