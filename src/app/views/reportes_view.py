import flet as ft

class ReportesView(ft.View):
    """Vista de Reportes"""
    def __init__(self):
        super().__init__(
            route="/home/reportes",
            controls=[
                ft.Text("Vista de Reportes", size=20)
            ]
        )
