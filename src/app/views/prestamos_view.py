import flet as ft

class PrestamosView(ft.View):
    """Vista de Préstamos"""
    def __init__(self):
        super().__init__(
            route="/home/prestamos",
            controls=[
                ft.Text("Vista de Préstamos", size=20)
            ]
        )
