import flet as ft

class PagosView(ft.View):
    """Vista de Pagos"""
    def __init__(self):
        super().__init__(
            route="/home/pagos",
            controls=[
                ft.Text("Vista de Pagos", size=20)
            ]
        )
