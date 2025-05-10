import flet as ft
from app.views.containers.pagos_container import PagosContainer

class PagosView(ft.View):
    """Vista de Pagos"""
    def __init__(self):
        super().__init__(
            route="/home/pagos",
            controls=[
                PagosContainer()
            ]
        )
