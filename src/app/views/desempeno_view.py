import flet as ft

class DesempenoView(ft.View):
    """Vista de Desempeño"""
    def __init__(self):
        super().__init__(
            route="/home/desempeno",
            controls=[
                ft.Text("Vista de Desempeño", size=20)
            ]
        )
