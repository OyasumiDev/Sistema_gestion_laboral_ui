import flet as ft
from app.views.containers.prestamos_container import PrestamosContainer

class PrestamosView(ft.View):
    """Vista de Préstamos"""
    def __init__(self):
        super().__init__(route="/home/prestamos")
        self.padding = 0
        self.scroll = ft.ScrollMode.AUTO
        # 👇 monta realmente el container en la vista
        self.controls = [
            PrestamosContainer()
        ]
